# -*- coding: utf-8 -*-
"""LOF/ETF 基金数据服务 — 直连东方财富 HTTP API

数据源：东方财富 push2.eastmoney.com（LOF + ETF 实时行情，含净值和溢价率）
替代原新浪 JSONP API（新浪不提供净值/溢价率）。
申购状态通过东方财富基金详情 API 获取。
连续溢价天数通过本地 JSON 快照计算。
"""

import json
import logging
import os
import time

from services.http_client import em_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

# ==================== 东方财富 push2 行情端点 ====================

_EM_PUSH_URL = 'https://push2.eastmoney.com/api/qt/clist/get'

# 分类码: LOF基金=b:MK0404, ETF基金=b:MK0403
_LOF_BOARD = 'b:MK0404'
_ETF_BOARD = 'b:MK0403'

# 字段: f12=代码, f14=名称, f2=最新价, f3=涨跌幅, f5=成交量, f6=成交额,
#        f161=基金净值, f168=溢价率
_EM_FIELDS = 'f12,f14,f2,f3,f5,f6,f161,f168'

# ==================== 东方财富基金详情端点（申购状态） ====================

_EM_FUND_DETAIL_URL = 'https://fundmobapi.eastmoney.com/FundMNewApi/FundMNFundInfo'

# 申购状态缓存: { code: { 'status': '不限', 'ts': timestamp } }
_purchase_cache = {}
_PURCHASE_CACHE_TTL = 3600  # 1 小时

# ==================== 连续溢价快照 ====================

_SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
_SNAPSHOT_FILE = os.path.join(_SNAPSHOT_DIR, 'lof_premium_snapshot.json')
_SNAPSHOT_MAX_DAYS = 30


def _fetch_em_fund_list(board):
    """从东方财富获取基金实时行情列表。

    替代原 _fetch_sina_fund_list()，使用 push2 API。
    """
    params = {
        'pn': 1,
        'pz': 500,
        'po': 1,
        'np': 1,
        'fltt': 2,
        'invt': 2,
        'fs': board,
        'fields': _EM_FIELDS,
    }
    try:
        resp = em_get(_EM_PUSH_URL, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f'[EmLof] HTTP {resp.status_code} (board={board})')
            return []
        data = resp.json()
        if not data or not data.get('data') or not data['data'].get('diff'):
            return []
        return data['data']['diff']
    except Exception as e:
        logger.warning(f'[EmLof] 获取基金列表失败(board={board}): {e}')
        return []


def _parse_em_fund_row(row):
    """解析单条东方财富基金行情数据。

    字段: f12=代码, f14=名称, f2=最新价, f3=涨跌幅, f5=成交量,
          f6=成交额, f161=基金净值, f168=溢价率
    """
    code = str(row.get('f12', '')).strip()
    if not code:
        return None

    # 交易所: 5开头=沪, 1开头=深
    if code.startswith('5'):
        exchange = '沪'
    elif code.startswith('1'):
        exchange = '深'
    else:
        exchange = ''

    name = str(row.get('f14', '')).strip()
    if not name:
        return None

    price = safe_float(row.get('f2'))
    valuation = safe_float(row.get('f161'))
    premium = safe_float(row.get('f168'))

    return {
        '代码': code,
        '名称': name,
        '交易所': exchange,
        '最新价': price,
        '涨跌幅': safe_float(row.get('f3')),
        '成交量': safe_float(row.get('f5')),
        '成交额': safe_float(row.get('f6')),
        '估值': valuation,
        '溢价率': premium,
        '连续溢价': 0,  # 由快照计算填充
        '申购状态': '不限',  # 由 _enrich_purchase_status 填充
    }


# ==================== 连续溢价快照逻辑 ====================

def _load_snapshot():
    """加载本地溢价快照 JSON 文件。"""
    try:
        if os.path.exists(_SNAPSHOT_FILE):
            with open(_SNAPSHOT_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f'[LofSnapshot] 加载快照失败: {e}')
    return {}


def _save_snapshot(snapshot):
    """保存溢价快照到 JSON 文件。"""
    try:
        os.makedirs(_SNAPSHOT_DIR, exist_ok=True)
        with open(_SNAPSHOT_FILE, 'w', encoding='utf-8') as f:
            json.dump(snapshot, f, ensure_ascii=False)
    except Exception as e:
        logger.warning(f'[LofSnapshot] 保存快照失败: {e}')


def _update_premium_snapshot(fund_list):
    """更新今日溢价快照，并返回每个基金的连续溢价天数。

    快照结构: { "2026-07-09": { "161725": true, ... }, ... }
    true = 当日溢价率 > 0
    """
    today = time.strftime('%Y-%m-%d')
    snapshot = _load_snapshot()

    # 如果今天还没有快照，创建今日快照
    if today not in snapshot:
        today_data = {}
        for item in fund_list:
            code = item.get('代码', '')
            premium = item.get('溢价率', 0)
            if code:
                today_data[code] = premium > 0
        snapshot[today] = today_data
        # 清理超过 30 天的旧快照
        sorted_dates = sorted(snapshot.keys())
        while len(sorted_dates) > _SNAPSHOT_MAX_DAYS:
            oldest = sorted_dates.pop(0)
            snapshot.pop(oldest, None)
        _save_snapshot(snapshot)

    # 计算每个基金的连续溢价天数
    sorted_dates = sorted(snapshot.keys(), reverse=True)
    consecutive_map = {}

    # 从今天往前数连续溢价天数
    all_codes = set()
    for d in sorted_dates:
        all_codes.update(snapshot[d].keys())

    for code in all_codes:
        count = 0
        for d in sorted_dates:
            if snapshot[d].get(code, False):
                count += 1
            else:
                break
        consecutive_map[code] = count

    return consecutive_map


# ==================== 申购状态获取 ====================

def _fetch_purchase_status(code):
    """从东方财富基金详情 API 获取申购状态。

    返回: '不限' / '暂停' / '限100'
    """
    params = {
        'FundCode': code,
        'deviceid': '1',
    }
    try:
        resp = em_get(_EM_FUND_DETAIL_URL, params=params, timeout=10)
        if resp.status_code != 200:
            return '不限'
        data = resp.json()
        # 列表数据在 Expansion 下的 DT_Serializer
        expansion = data.get('Expansion', {}) or {}
        purchase_status = expansion.get('PURCHASE', '')
        if not purchase_status:
            return '不限'

        if '暂停' in purchase_status or '停止' in purchase_status:
            return '暂停'
        if '限制' in purchase_status or '限' in purchase_status:
            return '限100'
        return '不限'
    except Exception:
        return '不限'


def _enrich_purchase_status(fund_list):
    """批量获取申购状态并填充到列表中。

    使用模块级缓存，TTL 1 小时。避免每次请求都逐个调用。
    """
    now = time.time()
    codes_to_fetch = []

    for item in fund_list:
        code = item.get('代码', '')
        cached = _purchase_cache.get(code)
        if cached and (now - cached['ts']) < _PURCHASE_CACHE_TTL:
            item['申购状态'] = cached['status']
        else:
            codes_to_fetch.append((item, code))

    for item, code in codes_to_fetch:
        status = _fetch_purchase_status(code)
        item['申购状态'] = status
        _purchase_cache[code] = { 'status': status, 'ts': now }


# ==================== 对外接口 ====================

def get_lof_list():
    """获取 LOF/ETF 基金列表（含净值、溢价率、连续溢价、申购状态）"""
    try:
        lof_rows = _fetch_em_fund_list(_LOF_BOARD)
        etf_rows = _fetch_em_fund_list(_ETF_BOARD)
        all_raw = lof_rows + etf_rows

        if not all_raw:
            return []

        result = []
        for row in all_raw:
            parsed = _parse_em_fund_row(row)
            if parsed:
                result.append(parsed)

        if not result:
            return []

        # 填充连续溢价天数
        try:
            consecutive_map = _update_premium_snapshot(result)
            for item in result:
                code = item.get('代码', '')
                item['连续溢价'] = consecutive_map.get(code, 0)
        except Exception as e:
            logger.warning(f'[LofList] 连续溢价计算失败: {e}')

        # 填充申购状态（异步降级：失败时保持默认"不限"）
        try:
            _enrich_purchase_status(result)
        except Exception as e:
            logger.warning(f'[LofList] 申购状态获取失败: {e}')

        return result
    except Exception as e:
        logger.warning(f'获取LOF列表失败: {e}')
        return []


def get_lof_opportunities():
    """获取 LOF 套利机会（按真实溢价率排序）"""
    try:
        lof_list = get_lof_list()
        if not lof_list:
            return {'premium': [], 'discount': []}

        sorted_premium = sorted(lof_list, key=lambda x: x.get('溢价率', 0), reverse=True)[:20]
        sorted_discount = sorted(lof_list, key=lambda x: x.get('溢价率', 0))[:20]

        return {
            'premium': sorted_premium,
            'discount': sorted_discount
        }
    except Exception as e:
        logger.warning(f'获取LOF套利机会失败: {e}')
        return {'premium': [], 'discount': []}


def get_lof_market_summary():
    """获取 LOF 市场概览（含溢价率统计）"""
    try:
        lof_list = get_lof_list()
        if not lof_list:
            return None

        premiums = [item.get('溢价率', 0) for item in lof_list]
        change_pcts = [item.get('涨跌幅', 0) for item in lof_list]
        up_count = sum(1 for c in change_pcts if c > 0)
        down_count = sum(1 for c in change_pcts if c < 0)
        positive_count = sum(1 for p in premiums if p > 0)
        discount_count = sum(1 for p in premiums if p < 0)
        total_amount = sum(item.get('成交额', 0) for item in lof_list)

        # 按交易所分组统计平均溢价
        boards = {}
        for item in lof_list:
            ex = item.get('交易所', '其他')
            if not ex:
                ex = '其他'
            if ex not in boards:
                boards[ex] = { 'count': 0, 'premium_sum': 0 }
            boards[ex]['count'] += 1
            boards[ex]['premium_sum'] += item.get('溢价率', 0)

        top_board = None
        top_board_avg = -float('inf')
        for board, stats in boards.items():
            avg = stats['premium_sum'] / stats['count'] if stats['count'] > 0 else 0
            if avg > top_board_avg:
                top_board_avg = avg
                top_board = board

        return {
            'count': len(lof_list),
            'up_count': up_count,
            'down_count': down_count,
            'up_rate': round(up_count / len(lof_list) * 100, 1) if lof_list else 0,
            'total_amount': round(total_amount / 1e8, 2),
            'avg_change': round(sum(change_pcts) / len(change_pcts), 2) if change_pcts else 0,
            # 溢价率统计
            'positive_count': positive_count,
            'discount_count': discount_count,
            'top_premium': round(max(premiums), 2) if premiums else 0,
            'premium_avg': round(sum(premiums) / len(premiums), 2) if premiums else 0,
            'top_premium_board': (top_board + '市') if top_board else '--',
            'top_board_premium_avg': round(top_board_avg, 2) if top_board else None,
        }
    except Exception as e:
        logger.warning(f'获取LOF市场概览失败: {e}')
        return None
# -*- coding: utf-8 -*-
"""LOF/ETF 基金数据服务 — 直连新浪 JSONP HTTP API，零 akshare 依赖

数据源：新浪财经 vip.stock.finance.sina.com.cn（LOF + ETF 实时行情，不封 IP）
替代 ak.fund_etf_category_sina(symbol='LOF基金') / ak.fund_lof_spot_em()。
"""

import json
import logging

from services.http_client import sina_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

# 新浪 LOF/ETF JSONP 端点（与封闭式基金同一 API，node 不同）
_SINA_FUND_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/jsonp.php/"
    "IO.XSRV2.CallbackList['da_yPT46_Ll7K6WD']/Market_Center.getHQNodeDataSimple"
)

# node 映射：lof_hq_fund=LOF基金, etf_hq_fund=ETF基金
_LOF_NODE = 'lof_hq_fund'
_ETF_NODE = 'etf_hq_fund'


def _parse_sina_jsonp(text):
    """解析新浪 JSONP 响应，提取 JSON 数组。"""
    if not text:
        return []
    start = text.find('([')
    if start < 0:
        return []
    inner = text[start + 1:-2]
    try:
        return json.loads(inner)
    except (json.JSONDecodeError, ValueError):
        return []


def _fetch_sina_fund_list(node):
    """从新浪获取基金实时行情列表。

    替代 ak.fund_etf_category_sina(symbol=...)，直连新浪 JSONP API。
    """
    params = {
        'page': '1',
        'num': '5000',
        'sort': 'symbol',
        'asc': '0',
        'node': node,
        '[object HTMLDivElement]': 'qvvne',
    }
    try:
        resp = sina_get(_SINA_FUND_URL, params=params, timeout=15)
        if resp.status_code != 200:
            logger.warning(f'[SinaLof] HTTP {resp.status_code}')
            return []
        return _parse_sina_jsonp(resp.text)
    except Exception as e:
        logger.warning(f'[SinaLof] 获取基金列表失败(node={node}): {e}')
        return []


def _parse_fund_row(row):
    """解析单条基金行情数据（新浪字段名映射）。

    新浪字段：symbol, name, trade, pricechange, changepercent,
              buy, sell, settlement, open, high, low, volume, amount, code
    """
    raw_symbol = str(row.get('symbol', ''))
    code = raw_symbol[2:] if raw_symbol.startswith(('sh', 'sz')) else raw_symbol
    if not code:
        return None

    if code.startswith('5'):
        exchange = '沪'
    elif code.startswith('1'):
        exchange = '深'
    else:
        exchange = ''

    return {
        '代码': code,
        '名称': str(row.get('name', '')).strip(),
        '交易所': exchange,
        '最新价': safe_float(row.get('trade')),
        '涨跌幅': safe_float(row.get('changepercent')),
        '涨跌额': safe_float(row.get('pricechange')),
        '成交量': safe_float(row.get('volume')),
        '成交额': safe_float(row.get('amount')),
        '昨收': safe_float(row.get('settlement')),
        '今开': safe_float(row.get('open')),
        '最高': safe_float(row.get('high')),
        '最低': safe_float(row.get('low')),
        # 新浪不提供估值/溢价率，留空待后续补充
        '估值': 0,
        '溢价率': 0,
        '连续溢价': 0,
        '申购状态': '不限',
    }


def get_lof_list():
    """获取 LOF/ETF 基金列表（含实时价格，不含溢价率——新浪不提供）"""
    try:
        lof_rows = _fetch_sina_fund_list(_LOF_NODE)
        etf_rows = _fetch_sina_fund_list(_ETF_NODE)
        all_rows = lof_rows + etf_rows

        if not all_rows:
            return []

        result = []
        for row in all_rows:
            parsed = _parse_fund_row(row)
            if parsed:
                result.append(parsed)
        return result
    except Exception as e:
        logger.warning(f'获取LOF列表失败: {e}')
        return []


def get_lof_opportunities():
    """获取 LOF 套利机会（新浪不提供溢价率，返回空列表）"""
    try:
        lof_list = get_lof_list()
        if not lof_list:
            return {'premium': [], 'discount': []}

        # 新浪不提供溢价率，按涨跌幅排序作为替代
        sorted_premium = sorted(lof_list, key=lambda x: x['涨跌幅'], reverse=True)[:20]
        sorted_discount = sorted(lof_list, key=lambda x: x['涨跌幅'])[:20]

        return {
            'premium': sorted_premium,
            'discount': sorted_discount
        }
    except Exception as e:
        logger.warning(f'获取LOF套利机会失败: {e}')
        return {'premium': [], 'discount': []}


def get_lof_market_summary():
    """获取 LOF 市场概览"""
    try:
        lof_list = get_lof_list()
        if not lof_list:
            return None

        change_pcts = [item['涨跌幅'] for item in lof_list]
        up_count = sum(1 for c in change_pcts if c > 0)
        down_count = sum(1 for c in change_pcts if c < 0)
        total_amount = sum(item.get('成交额', 0) for item in lof_list)

        return {
            'count': len(lof_list),
            'up_count': up_count,
            'down_count': down_count,
            'up_rate': round(up_count / len(lof_list) * 100, 1) if lof_list else 0,
            'total_amount': round(total_amount / 1e8, 2),  # 转为亿元
            'avg_change': round(sum(change_pcts) / len(change_pcts), 2) if change_pcts else 0,
        }
    except Exception as e:
        logger.warning(f'获取LOF市场概览失败: {e}')
        return None
