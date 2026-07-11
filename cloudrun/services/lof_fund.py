# -*- coding: utf-8 -*-
"""LOF premium-arbitrage market and execution-rule data.

This module intentionally covers only LOFs. ETFs, synthetic history and
exchange-level settlement guesses are excluded because none of them prove an
off-exchange subscription can be sold as an on-exchange LOF position.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from services.http_client import em_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

_CST = timezone(timedelta(hours=8))
_EM_LIST_URL = 'https://push2.eastmoney.com/api/qt/clist/get'
_EM_KLINE_URL = 'https://push2his.eastmoney.com/api/qt/stock/kline/get'
_LOF_BOARD = 'b:MK0404'
_RULES_FILE = Path(__file__).resolve().parents[1] / 'data' / 'lof_execution_rules.json'
_RULE_PATH_MAX_AGE_DAYS = 30
_SUBSCRIPTION_MAX_AGE_DAYS = 1
_MAX_LIQUIDITY_LOOKUPS = 20
_LIQUIDITY_CACHE_TTL_SECONDS = 60 * 60
_liquidity_cache = {}


def _now():
    return datetime.now(_CST)


def _parse_iso(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return parsed.astimezone(_CST) if parsed.tzinfo else parsed.replace(tzinfo=_CST)
    except ValueError:
        return None


def _is_current(value, max_age_days, now=None):
    checked_at = _parse_iso(value)
    if not checked_at:
        return False
    now = now or _now()
    return checked_at <= now <= checked_at + timedelta(days=max_age_days)


def _not_expired(value, now=None):
    expiry = _parse_iso(value)
    return bool(expiry and (now or _now()) <= expiry)


def _field_evidence(rule, field, max_age_days, now):
    source = (rule.get('sources') or {}).get(field) or {}
    checked_at = source.get('checked_at') or rule.get('checked_at')
    checked = _parse_iso(checked_at)
    if max_age_days == _SUBSCRIPTION_MAX_AGE_DAYS:
        current = bool(checked and checked.date() == now.date())
    else:
        current = _is_current(checked_at, max_age_days, now)
    current = bool(source.get('url')) and current
    return {
        'url': source.get('url'),
        'checked_at': checked_at,
        'current': current,
        'source_name': source.get('name'),
    }


def _load_execution_rules():
    """Load locally curated execution evidence without treating it as market data."""
    try:
        with _RULES_FILE.open('r', encoding='utf-8') as rule_file:
            data = json.load(rule_file)
        return data.get('funds') or {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning('[LOF] unable to load execution rules: %s', exc)
        return {}


def _resolve_execution_rule(code, now=None, rules=None):
    """Return the dated, field-level evidence for a fund's execution path."""
    now = now or _now()
    rule = (rules if rules is not None else _load_execution_rules()).get(str(code), {})
    override = rule.get('manual_override') or {}
    override_active = _not_expired(override.get('expires_at'), now)

    subscription = _field_evidence(rule, 'subscription', _SUBSCRIPTION_MAX_AGE_DAYS, now)
    custody = _field_evidence(rule, 'custody_transfer', _RULE_PATH_MAX_AGE_DAYS, now)
    sell_date = _field_evidence(rule, 'sell_available_date', _RULE_PATH_MAX_AGE_DAYS, now)

    subscription_open = rule.get('subscription_status') == 'open' and subscription['current']
    subscription_limit = rule.get('subscription_limit') if subscription_open else None
    custody_supported = rule.get('custody_transfer') is True and custody['current']
    expected_sell_date = rule.get('sell_available_date') if sell_date['current'] else None

    if override_active:
        subscription_open = override.get('subscription_open', subscription_open)
        subscription_limit = override.get('subscription_limit', subscription_limit)
        custody_supported = override.get('custody_transfer', custody_supported)
        expected_sell_date = override.get('sell_available_date', expected_sell_date)

    sell_date_value = _parse_iso(expected_sell_date)
    if sell_date_value and sell_date_value.date() < now.date():
        expected_sell_date = None

    trade_path_verified = bool(subscription_open and custody_supported and expected_sell_date)
    return {
        'subscription_status': '开放申购' if subscription_open else '待核验',
        'subscription_open': subscription_open,
        'subscription_limit': subscription_limit,
        'custody_transfer': custody_supported,
        'expected_sell_date': expected_sell_date,
        'trade_path_verified': trade_path_verified,
        'manual_override_active': override_active,
        'evidence': {
            'subscription': subscription,
            'custody_transfer': custody,
            'sell_available_date': sell_date,
        },
    }


def _timestamp_from_em(value):
    try:
        timestamp = int(value)
    except (TypeError, ValueError):
        return None
    if timestamp <= 0:
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000
    return datetime.fromtimestamp(timestamp, tz=_CST).isoformat()


def _fetch_em_lof_rows():
    params = {
        'pn': 1,
        'pz': 5000,
        'po': 1,
        'np': 1,
        'fltt': 2,
        'invt': 2,
        'fid': 'f168',
        'fs': _LOF_BOARD,
        'fields': 'f2,f3,f5,f6,f12,f13,f14,f124,f161,f168',
    }
    try:
        response = em_get(_EM_LIST_URL, params=params, timeout=20)
        if response.status_code != 200:
            return []
        return (response.json().get('data') or {}).get('diff') or []
    except Exception as exc:
        logger.warning('[LOF] market fetch failed: %s', exc)
        return []


def _market_for_code(code):
    return '1' if str(code).startswith(('5', '6')) else '0'


def _five_day_average_turnover(code):
    """Fetch a bounded number of public daily K-lines and cache the result."""
    cached = _liquidity_cache.get(code)
    now_ts = time.time()
    if cached and now_ts - cached['cached_at'] < _LIQUIDITY_CACHE_TTL_SECONDS:
        return cached['value']

    params = {
        'secid': f'{_market_for_code(code)}.{code}',
        'fields1': 'f1,f2,f3,f4,f5,f6',
        'fields2': 'f51,f52,f53,f54,f55,f56',
        'klt': 101,
        'fqt': 1,
        'lmt': 5,
    }
    value = None
    try:
        response = em_get(_EM_KLINE_URL, params=params, timeout=15)
        klines = ((response.json().get('data') or {}).get('klines') or [])
        amounts = []
        for line in klines:
            columns = str(line).split(',')
            if len(columns) >= 6:
                amount = safe_float(columns[5])
                if amount > 0:
                    amounts.append(amount)
        if amounts:
            value = round(sum(amounts) / len(amounts), 2)
    except Exception as exc:
        logger.info('[LOF] five-day turnover unavailable for %s: %s', code, exc)

    _liquidity_cache[code] = {'cached_at': now_ts, 'value': value}
    return value


def _parse_row(row, rule, fetched_at):
    code = str(row.get('f12') or '')
    price = safe_float(row.get('f2'))
    valuation = safe_float(row.get('f161'))
    premium = safe_float(row.get('f168'))
    quote_time = _timestamp_from_em(row.get('f124'))
    quote_date = _parse_iso(quote_time).date().isoformat() if quote_time else None
    valid_quote = bool(price > 0 and valuation > 0 and quote_date == fetched_at.date().isoformat())
    exchange = '沪' if str(row.get('f13')) == '1' else '深'

    return {
        '代码': code,
        '名称': str(row.get('f14') or '').strip(),
        '交易所': exchange,
        '最新价': price,
        '涨跌幅': safe_float(row.get('f3')),
        '成交量': safe_float(row.get('f5')),
        '成交额': safe_float(row.get('f6')),
        '估值': valuation,
        '溢价率': premium,
        '行情时间': quote_time,
        '净值日期': quote_date,
        '净值来源': '东方财富行情快照',
        '报价有效': valid_quote,
        '申购状态': rule['subscription_status'],
        '可申购': rule['subscription_open'],
        '单账户限额': rule['subscription_limit'],
        '可转托管': rule['custody_transfer'],
        '预计可卖出日': rule['expected_sell_date'],
        '交易路径已验证': rule['trade_path_verified'],
        '规则证据': rule['evidence'],
        '人工覆盖有效': rule['manual_override_active'],
        '近5日平均成交额': None,
    }


def get_lof_list():
    """Return LOF-only quotes enriched with auditable execution-rule evidence."""
    fetched_at = _now()
    rows = _fetch_em_lof_rows()
    rules = _load_execution_rules()
    result = []
    for row in rows:
        code = str(row.get('f12') or '')
        if not code:
            continue
        result.append(_parse_row(row, _resolve_execution_rule(code, fetched_at, rules), fetched_at))

    # K-line calls are intentionally bounded; absent history keeps a fund in observation.
    candidates = sorted(
        (
            item for item in result
            if item['报价有效'] and item['溢价率'] > 0 and item['交易路径已验证']
        ),
        key=lambda item: item['溢价率'],
        reverse=True,
    )[:_MAX_LIQUIDITY_LOOKUPS]
    for item in candidates:
        item['近5日平均成交额'] = _five_day_average_turnover(item['代码'])

    return result


def get_lof_opportunities():
    """Compatibility endpoint returning positive-premium LOFs, never ETFs or discounts."""
    items = [item for item in get_lof_list() if item['溢价率'] > 0]
    items.sort(key=lambda item: item['溢价率'], reverse=True)
    return {'premium': items, 'discount': []}


def get_lof_market_summary():
    items = get_lof_list()
    premiums = [item['溢价率'] for item in items]
    return {
        'count': len(items),
        'positive_count': sum(1 for premium in premiums if premium > 0),
        'valid_quote_count': sum(1 for item in items if item['报价有效']),
        'verified_path_count': sum(1 for item in items if item['交易路径已验证']),
        'top_premium': round(max(premiums), 2) if premiums else 0,
        'premium_avg': round(sum(premiums) / len(premiums), 2) if premiums else 0,
    }
