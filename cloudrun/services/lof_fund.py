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

from services.http_client import em_get, tencent_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

_CST = timezone(timedelta(hours=8))
_EM_LIST_URL = 'https://push2delay.eastmoney.com/api/qt/clist/get'
_TENCENT_QUOTE_URL = 'https://qt.gtimg.cn/q='
_TENCENT_KLINE_URL = 'https://web.ifzq.gtimg.cn/appstock/app/kline/kline'
_LOF_BOARD = 'b:MK0404'
_RULES_FILE = Path(__file__).resolve().parents[1] / 'data' / 'lof_execution_rules.json'
_RULE_PATH_MAX_AGE_DAYS = 30
_SUBSCRIPTION_MAX_AGE_DAYS = 1
_MAX_LIQUIDITY_LOOKUPS = 30
_LIQUIDITY_CACHE_TTL_SECONDS = 60 * 60
_QUOTE_BATCH_SIZE = 50
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


def _timestamp_from_tencent(value):
    """Parse Tencent's quote timestamp, which is supplied in China time."""
    text = str(value or '').strip()
    try:
        return datetime.strptime(text, '%Y%m%d%H%M%S').replace(tzinfo=_CST).isoformat()
    except ValueError:
        return None


def _latest_trading_weekday(now=None):
    """Return the latest weekday with a mainland-market close.

    The upstream quote is not updated on weekends. Keeping Friday's close
    available on Saturday/Sunday is materially different from treating it as
    a stale intraday quote. Public-holiday calendars are intentionally not
    guessed here: an older quote remains visible but is marked for review.
    """
    current = (now or _now()).date()
    while current.weekday() >= 5:
        current -= timedelta(days=1)
    return current


def _quote_is_current(quote_time, now=None):
    quote_at = _parse_iso(quote_time)
    return bool(quote_at and quote_at.date() == _latest_trading_weekday(now))


def _decode_tencent_rows(text):
    """Decode the public, GBK Tencent multi-security quote response."""
    rows = {}
    for chunk in str(text or '').split(';'):
        if '="' not in chunk:
            continue
        try:
            values = chunk.split('"', 2)[1].split('~')
        except IndexError:
            continue
        if len(values) < 82:
            continue
        code = str(values[2] or '').strip()
        if code:
            rows[code] = values
    return rows


def _fetch_em_lof_rows():
    """Fetch the LOF universe from Eastmoney's delayed quote directory.

    The legacy push2 host can abruptly close direct connections. The delayed
    directory remains public and is used only to enumerate the LOF board; the
    executable quote fields come from Tencent below.
    """
    base_params = {
        'pz': 100,
        'po': 1,
        'np': 1,
        'fltt': 2,
        'invt': 2,
        'fid': 'f3',
        'fs': _LOF_BOARD,
        'fields': 'f12,f13,f14',
    }
    result = []
    total = None
    page = 1
    try:
        while total is None or len(result) < total:
            response = em_get(_EM_LIST_URL, params={**base_params, 'pn': page}, timeout=20)
            if response.status_code != 200:
                break
            data = response.json().get('data') or {}
            total = int(data.get('total') or 0)
            rows = data.get('diff') or []
            if not rows:
                break
            result.extend(rows)
            page += 1
        return result
    except Exception as exc:
        logger.warning('[LOF] universe fetch failed: %s', exc)
        return []


def _fetch_tencent_quotes(universe):
    """Fetch price, latest unit NAV and close timestamp in bounded batches."""
    result = {}
    for start in range(0, len(universe), _QUOTE_BATCH_SIZE):
        batch = universe[start:start + _QUOTE_BATCH_SIZE]
        symbols = []
        for row in batch:
            code = str(row.get('f12') or '')
            if code:
                exchange = 'sh' if str(row.get('f13')) == '1' else 'sz'
                symbols.append(f'{exchange}{code}')
        if not symbols:
            continue
        try:
            response = tencent_get(f'{_TENCENT_QUOTE_URL}{",".join(symbols)}', timeout=20)
            if response.status_code == 200:
                result.update(_decode_tencent_rows(response.content.decode('gbk', 'replace')))
        except Exception as exc:
            logger.warning('[LOF] Tencent quote batch unavailable: %s', exc)
    return result


def _parse_row(row, quote_values, rule, fetched_at):
    """Join LOF membership with Tencent's price and latest unit-NAV fields."""
    code = str(row.get('f12') or '')
    values = quote_values or []
    price = safe_float(values[3] if len(values) > 3 else 0)
    valuation = safe_float(values[81] if len(values) > 81 else 0)
    quote_time = _timestamp_from_tencent(values[30] if len(values) > 30 else '')
    premium = round((price / valuation - 1) * 100, 4) if price > 0 and valuation > 0 else 0
    exchange = '沪' if str(row.get('f13')) == '1' else '深'
    security_type = str(values[61] if len(values) > 61 else '').strip()
    valid_quote = bool(
        security_type == 'LOF'
        and price > 0
        and valuation > 0
        and _quote_is_current(quote_time, fetched_at)
    )

    return {
        '代码': code,
        '名称': str(values[1] if len(values) > 1 else row.get('f14') or '').strip(),
        '交易所': exchange,
        '最新价': price,
        '涨跌幅': safe_float(values[32] if len(values) > 32 else 0),
        '成交量': safe_float(values[36] if len(values) > 36 else 0),
        # Tencent reports the amount in 万元.
        '成交额': safe_float(values[37] if len(values) > 37 else 0) * 10000,
        '估值': valuation,
        '溢价率': premium,
        '行情时间': quote_time,
        '净值日期': _parse_iso(quote_time).date().isoformat() if quote_time else None,
        '净值来源': '腾讯财经基金行情（最新单位净值）',
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


def _market_for_code(code):
    return 'sh' if str(code).startswith(('5', '6')) else 'sz'


def _five_day_average_turnover(code):
    """Calculate five-session turnover from Tencent daily bars."""
    cached = _liquidity_cache.get(code)
    now_ts = time.time()
    if cached and now_ts - cached['cached_at'] < _LIQUIDITY_CACHE_TTL_SECONDS:
        return cached['value']

    value = None
    params = {'param': f'{_market_for_code(code)}{code},day,,,5'}
    try:
        response = tencent_get(_TENCENT_KLINE_URL, params=params, timeout=15)
        data = response.json().get('data') or {}
        series = (data.get(f'{_market_for_code(code)}{code}') or {}).get('day') or []
        amounts = []
        for point in series[-5:]:
            if len(point) < 6:
                continue
            close = safe_float(point[2])
            volume = safe_float(point[5])
            if close > 0 and volume > 0:
                amounts.append(close * volume)
        if amounts:
            value = round(sum(amounts) / len(amounts), 2)
    except Exception as exc:
        logger.info('[LOF] five-day turnover unavailable for %s: %s', code, exc)

    _liquidity_cache[code] = {'cached_at': now_ts, 'value': value}
    return value


def get_lof_list():
    """Return LOF-only quotes enriched with auditable execution-rule evidence."""
    fetched_at = _now()
    rows = _fetch_em_lof_rows()
    quotes = _fetch_tencent_quotes(rows)
    rules = _load_execution_rules()
    result = []
    for row in rows:
        code = str(row.get('f12') or '')
        quote_values = quotes.get(code)
        if not code or not quote_values:
            continue
        item = _parse_row(
            row,
            quote_values,
            _resolve_execution_rule(code, fetched_at, rules),
            fetched_at,
        )
        # The market-board directory is only a universe. Tencent's explicit
        # security type is the final LOF-only guard against ETFs.
        if item['报价有效'] or str(quote_values[61]).strip() == 'LOF':
            result.append(item)

    # K-line calls are intentionally bounded; absent history keeps a fund in observation.
    candidates = sorted(
        (
            item for item in result
            if item['报价有效'] and item['溢价率'] > 0
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
