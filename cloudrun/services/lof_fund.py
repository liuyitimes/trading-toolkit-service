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
