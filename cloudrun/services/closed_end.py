# -*- coding: utf-8 -*-
"""封闭式基金数据获取 - 直连 HTTP（新浪 + 东财），零 akshare 依赖

数据源：
  - 新浪封闭式基金行情：vip.stock.finance.sina.com.cn（JSONP，实时价格，不封 IP）
  - 东方财富基金历史净值：api.fund.eastmoney.com/f10/lsjz（JSON，走 em_get 限流）

策略：
  实时接口先返回价格 + 空净值；后台串行拉取所有基金的最新净值后缓存（6 小时）。
  下次请求命中缓存即可计算折价率。

设计依据：ADR-001 / ADR-002 / ADR-005
  - 新浪 JSONP 端点直连，替代 ak.fund_etf_category_sina()
  - 东财 lsjz JSON 端点直连，替代 ak.fund_open_fund_info_em()（避免 pingzhongdata.js + py_mini_racer 依赖）
  - 净值批量拉取改为串行 em_get（遵循东财防封铁律：不并发），后台 daemon 线程执行
"""

import json
import logging
import time
from datetime import datetime, timezone, timedelta

from services.http_client import sina_get, em_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

CST = timezone(timedelta(hours=8))
_NAV_MAX_AGE_DAYS = 7

# ==================== 上游 API URL ====================

# 新浪封闭式基金列表（JSONP 包装，需手动剥离 callback）
_SINA_CLOSE_FUND_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/jsonp.php/"
    "IO.XSRV2.CallbackList['da_yPT46_Ll7K6WD']/Market_Center.getHQNodeDataSimple"
)

# 东财基金历史净值（标准 JSON，pageSize=1 取最新一条）
_EM_FUND_NAV_URL = "https://api.fund.eastmoney.com/f10/lsjz"

# ==================== 净值缓存（模块级，6 小时 TTL） ====================

_NAV_CACHE = {}
_NAV_CACHE_TTL = 6 * 3600
_BATCH_FETCHED_AT = 0


# ==================== 工具函数 ====================


def _parse_code(raw_code):
    """解析新浪 symbol（如 sz180901）→ (纯代码, 交易所中文)"""
    raw_code = str(raw_code).strip()
    if not raw_code:
        return '', ''
    if raw_code.startswith('sh'):
        return raw_code[2:], '沪'
    if raw_code.startswith('sz'):
        return raw_code[2:], '深'
    if raw_code and raw_code[0] in ('5', '6', '9'):
        return raw_code, '沪'
    if raw_code and raw_code[0] in ('1', '0'):
        return raw_code, '深'
    return raw_code, ''


def _parse_sina_jsonp(text):
    """解析新浪 JSONP 响应，提取 JSON 数组。

    响应格式：/*<script>...</script>*/IO.XSRV2.CallbackList['xxx']([{...},...]);
    提取策略：定位 '([' 后一位到末尾倒数第二位，得到 [{...},...]，再 json.loads。
    """
    if not text:
        return []
    start = text.find('([')
    if start < 0:
        return []
    inner = text[start + 1:-2]
    try:
        return json.loads(inner)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f'[ClosedEnd] 新浪 JSONP 解析失败: {e}')
        return []


# ==================== 新浪封闭式基金列表 ====================


def _fetch_sina_close_fund_list():
    """从新浪获取封闭式基金实时行情列表。

    替代 ak.fund_etf_category_sina(symbol='封闭式基金')。
    """
    params = {
        'page': '1',
        'num': '5000',
        'sort': 'symbol',
        'asc': '0',
        'node': 'close_fund',
        '[object HTMLDivElement]': 'qvvne',
    }
    resp = sina_get(_SINA_CLOSE_FUND_URL, params=params, timeout=15)
    if resp.status_code != 200:
        logger.warning(f'[ClosedEnd] 新浪封闭式基金列表 HTTP {resp.status_code}')
        return []
    return _parse_sina_jsonp(resp.text)


# ==================== 东财基金净值 ====================


def _fetch_one_nav(code):
    """获取单只基金最新净值（走 em_get 限流）。

    替代 ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势', period='1月')。
    使用 lsjz JSON 端点 pageSize=1，仅取最新一条，避免解析 pingzhongdata.js。
    """
    now = time.time()
    cached = _NAV_CACHE.get(code)
    if cached and now - cached['fetched_at'] < _NAV_CACHE_TTL:
        return cached

    try:
        params = {
            'fundCode': code,
            'pageIndex': '1',
            'pageSize': '1',
        }
        # lsjz 需要 Referer: fundf10.eastmoney.com（em_session 默认 Referer 是 data.eastmoney.com）
        headers = {'Referer': 'https://fundf10.eastmoney.com/'}
        resp = em_get(_EM_FUND_NAV_URL, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.warning(f'[ClosedEnd] 基金 {code} 净值 HTTP {resp.status_code}')
            result = {'nav': 0, 'date': '', 'fetched_at': now}
        else:
            d = resp.json()
            lsjz_list = (d.get('Data') or {}).get('LSJZList') or []
            if not lsjz_list:
                result = {'nav': 0, 'date': '', 'fetched_at': now}
            else:
                latest = lsjz_list[0]
                nav = safe_float(latest.get('DWJZ', 0))
                date = str(latest.get('FSRQ', ''))
                result = {'nav': nav, 'date': date, 'fetched_at': now}
    except Exception as e:
        logger.warning(f'[ClosedEnd] 获取基金 {code} 净值失败: {e}')
        result = {'nav': 0, 'date': '', 'fetched_at': now}

    _NAV_CACHE[code] = result
    return result


def _nav_is_current(nav_date, now=None):
    """A reported NAV is usable for an observation only while it is recent."""
    try:
        reported = datetime.strptime(str(nav_date)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return False
    current = (now or datetime.now(CST)).date()
    return 0 <= (current - reported).days <= _NAV_MAX_AGE_DAYS


def _batch_fetch_navs(codes):
    """串行批量拉取净值（遵循东财防封铁律：不并发）。

    em_get 内置 ≥1s 串行限流，~86 只基金约需 130s，在后台 daemon 线程执行。
    """
    global _BATCH_FETCHED_AT
    now = time.time()
    if _BATCH_FETCHED_AT and now - _BATCH_FETCHED_AT < _NAV_CACHE_TTL:
        return
    _BATCH_FETCHED_AT = now

    start = time.time()
    success = 0
    for c in codes:
        result = _fetch_one_nav(c)
        if result.get('nav'):
            success += 1
    logger.info(f'[ClosedEnd] 批量净值完成: {success}/{len(codes)} 只, 耗时 {time.time() - start:.1f}s')


# ==================== 对外公共函数（签名保持不变） ====================


def get_closed_end_list():
    """获取封闭式基金列表（含实时价格 + 缓存净值 + 折价率）"""
    try:
        rows = _fetch_sina_close_fund_list()
    except Exception as e:
        logger.warning(f'[ClosedEnd] 获取封闭式基金列表失败: {e}')
        return []

    if not rows:
        return []

    result = []
    for row in rows:
        # 新浪字段：symbol, name, trade, pricechange, changepercent,
        #           buy, sell, settlement, open, high, low, volume, amount, code
        raw_symbol = str(row.get('symbol', ''))
        code, exchange = _parse_code(raw_symbol)
        if not code:
            continue

        price = safe_float(row.get('trade'))
        prev_close = safe_float(row.get('settlement'))
        change_pct = safe_float(row.get('changepercent'))
        volume = safe_float(row.get('volume'))
        amount = safe_float(row.get('amount'))

        nav_info = _NAV_CACHE.get(code, {})
        nav = nav_info.get('nav', 0)
        nav_date = nav_info.get('date', '')

        nav_is_current = nav > 0 and _nav_is_current(nav_date)
        discount = ((nav - price) / nav * 100) if nav_is_current else None

        result.append({
            'code': code,
            'name': str(row.get('name', '')).strip(),
            'exchange': exchange,
            'price': price,
            'prev_close': prev_close,
            'change_pct': change_pct,
            'volume': int(volume) if volume else 0,
            'amount': amount,
            'nav': nav,
            'nav_date': nav_date,
            'discount': round(discount, 2) if discount is not None else None,
            'nav_is_current': nav_is_current,
            'maturity_date': '',
            'top_holdings': [],
            'type': '封闭式基金',
            'strategy_status': 'observation',
            'exit_event_verified': False,
            'exit_event_note': '未核验到期、清盘、开放或要约退出事件，不构成可执行套利。',
        })

    # 后台串行拉取净值（daemon 线程，不阻塞当前请求）
    try:
        from threading import Thread
        codes = [item['code'] for item in result if item['code']]
        Thread(target=_batch_fetch_navs, args=(codes,), daemon=True).start()
    except Exception as e:
        logger.warning(f'[ClosedEnd] 启动净值后台拉取失败: {e}')

    return result


def get_closed_end_summary():
    """获取封闭式基金汇总统计"""
    items = get_closed_end_list()
    if not items:
        return {}

    total = len(items)
    with_nav = [i for i in items if i.get('nav_is_current')]
    discounts = [i['discount'] for i in with_nav if i.get('discount') is not None]
    avg_discount = (sum(discounts) / len(discounts)) if discounts else 0
    high_discount_count = len([d for d in discounts if d >= 5])
    premium_count = len([d for d in discounts if d < 0])

    return {
        'count': total,
        'with_nav_count': len(with_nav),
        'avg_discount': round(avg_discount, 2),
        'high_discount_count': high_discount_count,
        'premium_count': premium_count,
        'verified_count': 0,
        'total_amount': round(sum(i.get('amount', 0) for i in items), 0),
    }
