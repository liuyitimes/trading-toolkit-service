# -*- coding: utf-8 -*-
"""公告解析服务 — 从巨潮资讯获取并解析可转债/配股发行结果公告

功能：
  1. 搜索巨潮资讯获取最新发行结果公告列表
  2. 下载公告 PDF 并用 pdfplumber 提取表格
  3. 解析原股东配售率/认配率等关键字段
  4. 存入本地 SQLite/PostgreSQL 数据库

数据源：巨潮资讯 (cninfo.com.cn)
  - 搜索接口: POST /new/hisAnnouncement/query
  - PDF 下载: http://static.cninfo.com.cn/{adjunctUrl}
"""

import io
import logging
import re
from datetime import datetime, timedelta

import pdfplumber

from services.http_client import cninfo_post, cninfo_get
from models.database import get_db_session
from models.placement import PlacementResult

logger = logging.getLogger('trading_toolkit')

# ==================== 常量 ====================

_CNINFO_SEARCH_URL = 'http://www.cninfo.com.cn/new/hisAnnouncement/query'
_CNINFO_PDF_BASE = 'http://static.cninfo.com.cn/'

# 可转债发行结果相关关键词
_CB_RESULT_KEYWORDS = [
    '向不特定对象发行可转换公司债券发行结果',
    '可转换公司债券发行结果',
    '可转债发行结果',
]

# 优先配售结果关键词（更早发布的公告，包含配售率数据）
_CB_ALLOCATION_KEYWORDS = [
    '向不特定对象发行可转换公司债券优先配售',
    '可转换公司债券优先配售结果',
    '可转债优先配售结果',
    '网上中签率及优先配售结果',
]

# 配股相关关键词
_STOCK_KEYWORDS = [
    '配股发行结果',
    '向原股东配售股份发行结果',
]


# ==================== 公告发现 ====================


def search_announcements(keywords, category='category_kzzq_szsh',
                         days_back=30, max_pages=3):
    """搜索巨潮资讯公告

    Args:
        keywords: 搜索关键词列表，依次尝试
        category: 公告类别代码（默认：可转债）
        days_back: 搜索最近多少天
        max_pages: 最多搜索几页

    Returns:
        list[dict]: 公告列表，每项包含 announcementId, title, pdfUrl, date 等
    """
    end_date = datetime.now().strftime('%Y-%m-%d')
    start_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    se_date = f'{start_date}~{end_date}'

    results = []
    seen_ids = set()

    for keyword in keywords:
        for page in range(1, max_pages + 1):
            try:
                data = {
                    'pageNum': str(page),
                    'pageSize': '30',
                    'column': '',          # 沪深两市
                    'tabName': 'fulltext',
                    'plate': '',
                    'stock': '',
                    'searchkey': keyword,
                    'secid': '',
                    'category': category,
                    'trade': '',
                    'seDate': se_date,
                    'sortName': '',
                    'sortType': '',
                    'isHLtitle': 'true',
                }
                resp = cninfo_post(_CNINFO_SEARCH_URL, data=data, timeout=15)
                if resp.status_code != 200:
                    logger.warning(f'巨潮搜索返回 {resp.status_code}: {keyword}')
                    break

                body = resp.json()
                announcements = body.get('announcements') or []
                if not announcements:
                    break

                for ann in announcements:
                    ann_id = str(ann.get('announcementId', ''))
                    if ann_id and ann_id not in seen_ids:
                        seen_ids.add(ann_id)
                        title = _clean_title(ann.get('announcementTitle', ''))
                        adjunct_url = ann.get('adjunctUrl', '')
                        # 公告时间戳（毫秒）转日期
                        ts = ann.get('announcementTime', 0)
                        ann_date = ''
                        if ts:
                            ann_date = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')

                        results.append({
                            'announcement_id': ann_id,
                            'title': title,
                            'pdf_url': f'{_CNINFO_PDF_BASE}{adjunct_url}' if adjunct_url else '',
                            'date': ann_date,
                            'sec_code': ann.get('secCode', ''),
                            'sec_name': ann.get('secName', ''),
                        })

                # 没有更多页了
                if not body.get('hasMore'):
                    break

            except Exception as e:
                logger.warning(f'巨潮搜索异常: {keyword} page={page}, {e}')
                break

    logger.info(f'巨潮搜索完成: 找到 {len(results)} 条公告')
    return results


def _clean_title(title):
    """去除公告标题中的 HTML 高亮标签"""
    return re.sub(r'</?em>', '', title)


# ==================== PDF 下载与解析 ====================


def download_and_parse(pdf_url):
    """下载 PDF 并提取表格文本

    Returns:
        list[list[list[str]]]: 表格列表，每个表格是二维字符串数组
        失败返回空列表
    """
    try:
        resp = cninfo_get(pdf_url, timeout=30)
        if resp.status_code != 200:
            logger.warning(f'PDF 下载失败 {resp.status_code}: {pdf_url}')
            return []

        tables = []
        with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
            for page in pdf.pages:
                page_tables = page.extract_tables()
                for table in page_tables:
                    if table and len(table) >= 2:
                        tables.append(table)
        return tables

    except Exception as e:
        logger.warning(f'PDF 解析异常: {pdf_url}, {e}')
        return []


def parse_placement_from_tables(tables, title=''):
    """从公告表格中解析配售数据

    公告表格的典型结构：
    ┌──────────────┬──────────────┬──────────────┐
    │ 类别          │ 认购数量(张)  │ 认购金额(元)  │
    ├──────────────┼──────────────┼──────────────┤
    │ 原股东        │ 1,472,353    │ 1,472,353,000│
    │ 网上社会公众… │ 515,524      │ 515,524,000  │
    │ 网下机构投资者│ -            │ -            │
    │ 合计          │ 2,000,000    │ 2,000,000,000│
    └──────────────┴──────────────┴──────────────┘

    Returns:
        dict: 解析结果，包含以下字段（未找到的字段为 None）:
            - shareholder_amount: 原股东认购金额（亿元）
            - shareholder_quantity: 原股东认购数量（张）
            - online_amount: 网上公众认购金额（亿元）
            - total_amount: 发行总规模（亿元）
            - underwriter_amount: 主承销商包销金额（亿元）
            - shareholder_ratio: 原股东配售率（%）
            - online_ratio: 网上中签率（%）
    """
    result = {
        'shareholder_amount': None,
        'shareholder_quantity': None,
        'online_amount': None,
        'total_amount': None,
        'underwriter_amount': None,
        'shareholder_ratio': None,
        'online_ratio': None,
    }

    if not tables:
        return result

    for table in tables:
        _parse_single_table(table, result, title)

    # 计算配售率
    if result['total_amount'] and result['total_amount'] > 0:
        if result['shareholder_amount'] is not None:
            result['shareholder_ratio'] = round(
                result['shareholder_amount'] / result['total_amount'] * 100, 2
            )

    return result


def _parse_single_table(table, result, title=''):
    """解析单个表格，提取配售数据"""
    # 将表格转为统一的字符串列表（去除 None、去除空白）
    cleaned = []
    for row in table:
        cleaned_row = []
        for cell in row:
            if cell is None:
                cleaned_row.append('')
            else:
                cleaned_row.append(str(cell).strip())
        cleaned.append(cleaned_row)

    if not cleaned:
        return

    # 判断表格类型：查找表头行
    header_row_idx = -1
    for i, row in enumerate(cleaned):
        row_text = ''.join(row)
        if any(kw in row_text for kw in ['认购', '获配', '申购']):
            header_row_idx = i
            break

    if header_row_idx < 0:
        return

    headers = cleaned[header_row_idx]
    data_rows = cleaned[header_row_idx + 1:]

    # 识别金额列和数量列
    amount_col = -1
    quantity_col = -1
    ratio_col = -1
    for j, h in enumerate(headers):
        if '金额' in h or '获配金额' in h or '认购金额' in h:
            amount_col = j
        if '数量' in h or '获配数量' in h or '申购数量' in h or '认购数量' in h:
            quantity_col = j
        if '中签率' in h or '配售率' in h or '获配比例' in h:
            ratio_col = j

    # 遍历数据行，按关键词匹配
    for row in data_rows:
        if not row or not row[0]:
            continue
        row_label = row[0]

        # 原股东行
        if any(kw in row_label for kw in ['原股东', '优先配售', '控股股东']):
            if '一致行动人' in row_label:
                continue  # 跳过子行
            if amount_col >= 0 and amount_col < len(row):
                result['shareholder_amount'] = _parse_amount(row[amount_col])
            if quantity_col >= 0 and quantity_col < len(row):
                result['shareholder_quantity'] = _parse_quantity(row[quantity_col])
            if ratio_col >= 0 and ratio_col < len(row):
                result['shareholder_ratio'] = _parse_ratio(row[ratio_col])

        # 网上社会公众投资者行
        elif any(kw in row_label for kw in ['社会公众', '网上投资者', '网上公众', '社会公众投资者']):
            if amount_col >= 0 and amount_col < len(row):
                result['online_amount'] = _parse_amount(row[amount_col])
            if ratio_col >= 0 and ratio_col < len(row):
                result['online_ratio'] = _parse_ratio(row[ratio_col])

        # 合计行
        elif '合计' in row_label:
            if amount_col >= 0 and amount_col < len(row):
                result['total_amount'] = _parse_amount(row[amount_col])

        # 主承销商包销行
        elif any(kw in row_label for kw in ['主承销商', '包销', '承销商']):
            if amount_col >= 0 and amount_col < len(row):
                result['underwriter_amount'] = _parse_amount(row[amount_col])


def _parse_amount(text):
    """解析金额字段，返回亿元为单位的浮点数

    公告中金额单位通常为「元」或「万元」，需统一转为亿元。
    """
    if not text or text in ('-', '—', '/', ''):
        return None
    # 去除千分位逗号、空格
    text = text.replace(',', '').replace(' ', '').replace('\u3000', '')
    try:
        value = float(text)
    except ValueError:
        # 尝试提取数字部分
        m = re.search(r'[\d.]+', text)
        if m:
            try:
                value = float(m.group())
            except ValueError:
                return None
        else:
            return None

    # 判断单位并转换为亿元
    # 如果数值极大（>100亿以元为单位），说明单位是元
    if abs(value) >= 1e8:
        return round(value / 1e8, 4)
    elif abs(value) >= 1e4:
        # 可能是万元
        return round(value / 1e4, 4)
    else:
        # 可能已经是亿元
        return round(value, 4)


def _parse_quantity(text):
    """解析数量字段（张），返回整数"""
    if not text or text in ('-', '—', '/', ''):
        return None
    text = text.replace(',', '').replace(' ', '').replace('\u3000', '')
    try:
        return int(float(text))
    except ValueError:
        m = re.search(r'[\d.]+', text)
        if m:
            try:
                return int(float(m.group()))
            except ValueError:
                return None
        return None


def _parse_ratio(text):
    """解析比率字段，返回百分比数值"""
    if not text or text in ('-', '—', '/', ''):
        return None
    text = text.strip().replace(' ', '')
    # 已经是百分比格式，如 "85.32%"
    if '%' in text:
        try:
            return float(text.replace('%', ''))
        except ValueError:
            return None
    # 纯数字，可能是小数形式如 "0.8532"
    try:
        value = float(text)
        if 0 < value <= 1:
            return round(value * 100, 4)
        return round(value, 4)
    except ValueError:
        return None


# ==================== 数据库操作 ====================


def save_placement_result(data, announcement_id, source_url=''):
    """保存或更新配售结果到数据库

    Args:
        data: parse_placement_from_tables 返回的 dict
        announcement_id: 巨潮公告 ID
        source_url: 公告 PDF URL

    Returns:
        PlacementResult 或 None
    """
    if not data or not announcement_id:
        return None

    with get_db_session() as db:
        # 查找是否已存在
        existing = db.query(PlacementResult).filter_by(
            announcement_id=announcement_id
        ).first()

        if existing:
            # 更新已有记录
            for key in ['shareholder_amount', 'shareholder_ratio',
                        'online_amount', 'online_ratio',
                        'underwriter_amount']:
                if data.get(key) is not None:
                    setattr(existing, key, data[key])
            existing.source_url = source_url
            return existing
        else:
            record = PlacementResult(
                stock_code=data.get('stock_code', ''),
                stock_name=data.get('stock_name', ''),
                bond_code=data.get('bond_code', ''),
                bond_name=data.get('bond_name', ''),
                asset_type=data.get('asset_type', 'bond'),
                issue_size=data.get('total_amount'),
                shareholder_amount=data.get('shareholder_amount'),
                shareholder_ratio=data.get('shareholder_ratio'),
                online_amount=data.get('online_amount'),
                online_ratio=data.get('online_ratio'),
                underwriter_amount=data.get('underwriter_amount'),
                announce_date=data.get('announce_date', ''),
                announcement_id=announcement_id,
                source_url=source_url,
            )
            db.add(record)
            return record


def get_placement_by_stock(stock_code):
    """按股票代码查询配售结果"""
    with get_db_session() as db:
        record = db.query(PlacementResult).filter_by(
            stock_code=stock_code
        ).order_by(PlacementResult.announce_date.desc()).first()
        if record:
            return {
                'stock_code': record.stock_code,
                'stock_name': record.stock_name,
                'bond_code': record.bond_code,
                'bond_name': record.bond_name,
                'asset_type': record.asset_type,
                'issue_size': record.issue_size,
                'shareholder_amount': record.shareholder_amount,
                'shareholder_ratio': record.shareholder_ratio,
                'online_amount': record.online_amount,
                'online_ratio': record.online_ratio,
                'underwriter_amount': record.underwriter_amount,
                'announce_date': record.announce_date,
                'source_url': record.source_url,
            }
    return None


def get_all_placements(asset_type=None):
    """查询所有配售结果"""
    with get_db_session() as db:
        query = db.query(PlacementResult)
        if asset_type:
            query = query.filter_by(asset_type=asset_type)
        records = query.order_by(PlacementResult.announce_date.desc()).all()
        return [
            {
                'stock_code': r.stock_code,
                'stock_name': r.stock_name,
                'bond_code': r.bond_code,
                'bond_name': r.bond_name,
                'asset_type': r.asset_type,
                'issue_size': r.issue_size,
                'shareholder_amount': r.shareholder_amount,
                'shareholder_ratio': r.shareholder_ratio,
                'online_amount': r.online_amount,
                'online_ratio': r.online_ratio,
                'underwriter_amount': r.underwriter_amount,
                'announce_date': r.announce_date,
                'source_url': r.source_url,
            }
            for r in records
        ]


# ==================== 主流程：同步公告数据 ====================


def sync_cb_placement_announcements(days_back=30):
    """同步可转债配售/发行结果公告

    完整流程：搜索 → 过滤已入库 → 下载PDF → 解析 → 存库

    Args:
        days_back: 搜索最近多少天的公告

    Returns:
        dict: {'new': 新增条数, 'updated': 更新条数, 'failed': 失败条数}
    """
    stats = {'new': 0, 'updated': 0, 'failed': 0, 'skipped': 0}

    # 1. 搜索公告
    keywords = _CB_RESULT_KEYWORDS + _CB_ALLOCATION_KEYWORDS
    announcements = search_announcements(keywords, days_back=days_back)
    if not announcements:
        logger.info('未找到新的可转债发行结果公告')
        return stats

    # 2. 过滤已入库的公告
    with get_db_session() as db:
        existing_ids = {
            r.announcement_id
            for r in db.query(PlacementResult.announcement_id).all()
            if r.announcement_id
        }

    # 3. 逐条处理
    for ann in announcements:
        ann_id = ann['announcement_id']
        title = ann['title']
        pdf_url = ann['pdf_url']

        if not pdf_url:
            stats['skipped'] += 1
            continue

        # 如果已入库且不需要更新，跳过
        if ann_id in existing_ids:
            stats['skipped'] += 1
            continue

        try:
            # 下载并解析 PDF
            tables = download_and_parse(pdf_url)
            if not tables:
                logger.warning(f'公告解析无表格: {title} ({pdf_url})')
                stats['failed'] += 1
                continue

            # 解析配售数据
            data = parse_placement_from_tables(tables, title)

            # 补充公告元信息
            data['stock_code'] = ann.get('sec_code', '')
            data['stock_name'] = ann.get('sec_name', '')
            data['asset_type'] = 'bond'
            data['announce_date'] = ann.get('date', '')

            # 尝试从标题中提取转债名称
            bond_name = _extract_bond_name(title)
            if bond_name:
                data['bond_name'] = bond_name

            # 存库
            record = save_placement_result(data, ann_id, pdf_url)
            if record:
                if ann_id in existing_ids:
                    stats['updated'] += 1
                else:
                    stats['new'] += 1
                    existing_ids.add(ann_id)

            logger.info(f'公告解析成功: {title} → 股东配售率={data.get("shareholder_ratio")}%')

        except Exception as e:
            logger.warning(f'公告处理失败: {title}, {e}')
            stats['failed'] += 1

    logger.info(f'同步完成: new={stats["new"]}, updated={stats["updated"]}, '
                f'failed={stats["failed"]}, skipped={stats["skipped"]}')
    return stats


def sync_stock_placement_announcements(days_back=90):
    """同步股票配股发行结果公告

    与可转债类似，但搜索范围更大（配股公告更少，需要更长时间窗口）
    """
    stats = {'new': 0, 'updated': 0, 'failed': 0, 'skipped': 0}

    keywords = _STOCK_KEYWORDS
    # 配股公告不在可转债类别下，需要搜索全部分类
    announcements = search_announcements(
        keywords, category='', days_back=days_back
    )
    if not announcements:
        logger.info('未找到新的配股发行结果公告')
        return stats

    with get_db_session() as db:
        existing_ids = {
            r.announcement_id
            for r in db.query(PlacementResult.announcement_id).all()
            if r.announcement_id
        }

    for ann in announcements:
        ann_id = ann['announcement_id']
        title = ann['title']
        pdf_url = ann['pdf_url']

        if not pdf_url or ann_id in existing_ids:
            stats['skipped'] += 1
            continue

        try:
            tables = download_and_parse(pdf_url)
            if not tables:
                stats['failed'] += 1
                continue

            data = parse_placement_from_tables(tables, title)
            data['stock_code'] = ann.get('sec_code', '')
            data['stock_name'] = ann.get('sec_name', '')
            data['asset_type'] = 'stock'
            data['announce_date'] = ann.get('date', '')

            record = save_placement_result(data, ann_id, pdf_url)
            if record:
                stats['new'] += 1
                existing_ids.add(ann_id)

            logger.info(f'配股公告解析成功: {title} → 认配率={data.get("shareholder_ratio")}%')

        except Exception as e:
            logger.warning(f'配股公告处理失败: {title}, {e}')
            stats['failed'] += 1

    logger.info(f'配股同步完成: new={stats["new"]}, failed={stats["failed"]}')
    return stats


def _extract_bond_name(title):
    """从公告标题中提取可转债名称

    标题格式示例：
    - "科博达向不特定对象发行可转换公司债券发行结果公告"
    - "湖北宜化化工股份有限公司向不特定对象发行可转换公司债券网上中签率及优先配售结果公告"
    """
    # 匹配 "XX向不特定对象" 或 "XX可转换公司债券" 前面的公司/转债名
    patterns = [
        r'^([^向]+?)向不特定对象发行可转换',
        r'^(.+?)(?:向不特定对象)?发行可转换公司债券',
    ]
    for pattern in patterns:
        m = re.match(pattern, title)
        if m:
            name = m.group(1).strip()
            # 去除公司后缀
            name = re.sub(r'(股份有限公司|有限公司|集团)$', '', name)
            if 2 <= len(name) <= 10:
                return name
    return None
