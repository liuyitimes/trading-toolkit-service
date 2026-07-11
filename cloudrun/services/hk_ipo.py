# -*- coding: utf-8 -*-
"""新股 IPO 数据服务（港股新股申购数据，数据源同花顺）

直连同花顺 data.10jqka.com.cn，零 akshare 依赖。
THS 页面为 GBK 编码 HTML，用 pandas.read_html 解析表格。
"""

import io
import logging
import re
from datetime import date, datetime

import pandas as pd

from services.http_client import ths_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

_THS_IPO_URL = "https://data.10jqka.com.cn/ipo/xgsgyzq/hkstock/"


def _fetch_ths_ipo_df():
    """从同花顺获取港股新股申购表格。

    替代 ak.stock_ipo_hk_ths()。
    THS 页面 GBK 编码，pd.read_html 解析后取含数据的表格（通常 2 张：表头 + 数据）。
    """
    resp = ths_get(_THS_IPO_URL, timeout=15)
    if resp.status_code != 200:
        logger.warning(f'[HkIpo] 同花顺 IPO HTTP {resp.status_code}')
        return pd.DataFrame()
    resp.encoding = 'gbk'  # THS 页面是 GBK 编码
    try:
        dfs = pd.read_html(io.StringIO(resp.text))
    except Exception as e:
        logger.warning(f'[HkIpo] pd.read_html 解析失败: {e}')
        return pd.DataFrame()
    if not dfs:
        return pd.DataFrame()
    # 取有数据行的最后一张表（第一张通常是纯表头）
    for df in reversed(dfs):
        if df.shape[0] > 0:
            return df
    return dfs[-1]


def _strip_html(text):
    """剥离 HTML 标签"""
    if not text:
        return ''
    return re.sub(r'<[^>]+>', '', str(text)).strip()


def _parse_date(text):
    """解析日期文本，统一为 YYYY-MM-DD 格式"""
    text = _strip_html(text)
    if not text or text == '-':
        return ''
    # 已经是完整日期
    if re.match(r'^\d{4}-\d{2}-\d{2}$', text):
        return text
    # 月-日 格式，补充当前年份
    m = re.match(r'^(\d{1,2})-(\d{1,2})', text)
    if m:
        from datetime import datetime
        year = datetime.now().year
        return f"{year}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"
    return text


def _classify_status(apply_date, list_date, today=None):
    """Classify an A-share IPO by its published dates, never by list presence.

    The legacy endpoint name is retained for compatibility, but the source is an
    A-share IPO table.  A row is actionable only on its application date; all
    other rows are historical or pending observations.
    """
    current = today or date.today()

    def parse(value):
        try:
            return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
        except (TypeError, ValueError):
            return None

    apply_day = parse(apply_date)
    list_day = parse(list_date)
    if list_day and list_day <= current:
        return 'listed'
    if apply_day == current:
        return 'open'
    if apply_day and apply_day > current:
        return 'upcoming'
    return 'pending'


def _parse_ipo_row(row):
    """解析单行 IPO 数据，统一字段映射"""
    list_date = str(row.get('上市日期', ''))
    win_rate = str(row.get('中签率（%）', ''))
    pe_ratio = str(row.get('发行市盈率', ''))
    industry_pe = str(row.get('行业市盈率', ''))
    apply_code = _strip_html(row.get('申购代码', ''))
    apply_date = _parse_date(row.get('申购日期', ''))
    list_date_parsed = _parse_date(list_date)
    pay_date = _parse_date(row.get('中签缴款日期', ''))

    pe_val = safe_float(pe_ratio.replace('-', '0') if pe_ratio else 0, 0)
    ind_val = safe_float(industry_pe.replace('-', '0') if industry_pe else 0, 0)

    status = _classify_status(apply_date, list_date_parsed)
    pe_available = bool(pe_ratio and pe_ratio != '-' and industry_pe and industry_pe != '-')

    return {
        'code': str(row.get('股票代码', '')),
        'name': str(row.get('股票简称', '')),
        'apply_code': apply_code,
        'ipo_price': safe_float(row.get('发行价格', 0), 0),
        'issue_total': safe_float(row.get('发行总数（万股）', 0), 0),
        'online_issue': safe_float(row.get('网上发行（万股）', 0), 0),
        'apply_limit': safe_float(row.get('申购上限（万股）', 0), 0),
        'top_value': safe_float(row.get('顶格申购需配市值（万元）', 0), 0),
        'apply_date': apply_date,
        'pay_date': pay_date,
        'list_date': list_date_parsed,
        'win_rate': _strip_html(win_rate) if win_rate != '-' else '',
        'pe_ratio': pe_ratio if pe_ratio != '-' else '',
        'industry_pe': industry_pe if industry_pe != '-' else '',
        'pe_diff': round(pe_val - ind_val, 2) if pe_available else None,
        'pe_available': pe_available,
        'first_day_gain': str(row.get('首日最高涨幅', '')) if str(row.get('首日最高涨幅', '')) != '-' else '',
        'plate_gain': str(row.get('打新收益（元）', '')) if str(row.get('打新收益（元）', '')) != '-' else '',
        'continuous_days': str(row.get('连板天数', '')) if str(row.get('连板天数', '')) != '-' else '',
        'status': status,
        # The source does not establish broker channel, market-value eligibility
        # or account capability.  It is deliberately an observation list.
        'strategy_status': 'observation',
        'source_market': 'A股',
    }


def get_hk_ipo_list():
    """获取新股 IPO 列表"""
    try:
        df = _fetch_ths_ipo_df()
        if df is None or df.empty:
            return []
        return [_parse_ipo_row(row) for _, row in df.iterrows()]
    except Exception as e:
        logger.warning(f'获取新股IPO列表失败: {e}')
        return []


def get_hk_ipo_upcoming():
    """获取今日可申购的 A 股新股（保留旧函数名以兼容 API 路由）。"""
    try:
        df = _fetch_ths_ipo_df()
        if df is None or df.empty:
            return []
        items = [_parse_ipo_row(row) for _, row in df.iterrows()]
        return [item for item in items if item['status'] == 'open']
    except Exception as e:
        logger.warning(f'获取即将上市新股失败: {e}')
        return []


def get_hk_ipo_detail(code):
    """获取指定新股 IPO 详情"""
    try:
        items = get_hk_ipo_list()
        for item in items:
            if item.get('code') == str(code):
                return item
        return None
    except Exception as e:
        logger.warning(f'获取新股IPO详情失败: {e}')
        return None


def get_hk_ipo_summary():
    """获取新股申购市场概览"""
    try:
        df = _fetch_ths_ipo_df()
        if df is None or df.empty:
            return {'upcoming_count': 0, 'recent_count': 0, 'total': 0}
        items = [_parse_ipo_row(row) for _, row in df.iterrows()]
        return {
            'upcoming_count': sum(item['status'] == 'open' for item in items),
            'recent_count': sum(item['status'] == 'listed' for item in items),
            'total': len(items),
            'source_market': 'A股',
        }
    except Exception as e:
        logger.warning(f'获取新股申购概览失败: {e}')
        return {'error': str(e)}
