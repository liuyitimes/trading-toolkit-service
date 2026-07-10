# -*- coding: utf-8 -*-
"""封闭式基金数据获取 - 基于新浪财经接口 + 净值异步补充

数据源:
  - ak.fund_etf_category_sina(symbol='封闭式基金')  实时价格列表
  - ak.fund_open_fund_info_em(symbol=code)          单只基金历史净值

策略:
  实时接口先返回价格 + 空净值; 后台并发拉取所有基金的最新净值后缓存 (6 小时).
  下次请求命中缓存即可计算折价率.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta

import akshare as ak
import pandas as pd

from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

CST = timezone(timedelta(hours=8))

_NAV_CACHE = {}
_NAV_CACHE_TTL = 6 * 3600
_BATCH_FETCHED_AT = 0


def _parse_code(raw_code):
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


def _fetch_one_nav(code):
    now = time.time()
    cached = _NAV_CACHE.get(code)
    if cached and now - cached['fetched_at'] < _NAV_CACHE_TTL:
        return cached

    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator='单位净值走势', period='1月')
        if df is None or df.empty:
            result = {'nav': 0, 'date': '', 'fetched_at': now}
        else:
            latest = df.iloc[-1]
            nav = safe_float(latest.get('单位净值', 0))
            date = str(latest.get('净值日期', ''))
            result = {'nav': nav, 'date': date, 'fetched_at': now}
        _NAV_CACHE[code] = result
        return result
    except Exception as e:
        logger.warning(f'获取基金 {code} 净值失败: {e}')
        result = {'nav': 0, 'date': '', 'fetched_at': now}
        _NAV_CACHE[code] = result
        return result


def _batch_fetch_navs(codes, max_workers=8, timeout=15):
    global _BATCH_FETCHED_AT
    now = time.time()
    if _BATCH_FETCHED_AT and now - _BATCH_FETCHED_AT < _NAV_CACHE_TTL:
        return
    _BATCH_FETCHED_AT = now

    start = time.time()
    success = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(_fetch_one_nav, c): c for c in codes}
        for fut in as_completed(futures, timeout=timeout):
            try:
                result = fut.result()
                if result.get('nav'):
                    success += 1
            except Exception:
                pass
    logger.info(f'批量获取净值完成: {success}/{len(codes)} 只, 耗时 {time.time() - start:.1f}s')


def get_closed_end_list():
    try:
        df = ak.fund_etf_category_sina(symbol='封闭式基金')
    except Exception as e:
        logger.warning(f'获取封闭式基金列表失败: {e}')
        return []

    if df is None or df.empty:
        return []

    result = []
    for _, row in df.iterrows():
        raw_code = str(row.get('代码', ''))
        code, exchange = _parse_code(raw_code)
        if not code:
            continue

        price = safe_float(row.get('最新价'))
        prev_close = safe_float(row.get('昨收'))
        change_pct = safe_float(row.get('涨跌幅'))
        volume = safe_float(row.get('成交量'))
        amount = safe_float(row.get('成交额'))

        nav_info = _NAV_CACHE.get(code, {})
        nav = nav_info.get('nav', 0)
        nav_date = nav_info.get('date', '')

        discount = ((nav - price) / nav * 100) if nav > 0 else 0

        result.append({
            'code': code,
            'name': str(row.get('名称', '')).strip(),
            'exchange': exchange,
            'price': price,
            'prev_close': prev_close,
            'change_pct': change_pct,
            'volume': int(volume) if volume else 0,
            'amount': amount,
            'nav': nav,
            'nav_date': nav_date,
            'discount': round(discount, 2),
            'maturity_date': '',
            'top_holdings': [],
            'type': '封闭式基金',
        })

    try:
        from threading import Thread
        codes = [item['code'] for item in result if item['code']]
        Thread(target=_batch_fetch_navs, args=(codes,), daemon=True).start()
    except Exception as e:
        logger.warning(f'启动净值后台拉取失败: {e}')

    return result


def get_closed_end_summary():
    items = get_closed_end_list()
    if not items:
        return {}

    total = len(items)
    with_nav = [i for i in items if i.get('nav', 0) > 0]
    discounts = [i['discount'] for i in with_nav if i.get('discount')]
    avg_discount = (sum(discounts) / len(discounts)) if discounts else 0
    high_discount_count = len([d for d in discounts if d >= 5])
    premium_count = len([d for d in discounts if d < 0])

    return {
        'count': total,
        'with_nav_count': len(with_nav),
        'avg_discount': round(avg_discount, 2),
        'high_discount_count': high_discount_count,
        'premium_count': premium_count,
        'total_amount': round(sum(i.get('amount', 0) for i in items), 0),
    }
