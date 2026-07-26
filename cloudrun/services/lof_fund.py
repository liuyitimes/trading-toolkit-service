# -*- coding: utf-8 -*-
"""LOF premium-arbitrage market and execution-rule data.

This module intentionally covers only LOFs. ETFs, synthetic history and
exchange-level settlement guesses are excluded because none of them prove an
off-exchange subscription can be sold as an on-exchange LOF position.
"""

import json
import logging
import math
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
_THEME_TAXONOMY_FILE = Path(__file__).resolve().parents[1] / 'data' / 'lof_theme_taxonomy.json'
_DAILY_SUBSCRIPTIONS_FILE = Path(__file__).resolve().parents[1] / 'data' / 'lof_daily_subscription_records.json'
_RULE_PATH_MAX_AGE_DAYS = 30
_SUBSCRIPTION_MAX_AGE_DAYS = 1
_MAX_LIQUIDITY_LOOKUPS = 30
_LIQUIDITY_CACHE_TTL_SECONDS = 60 * 60
_QUOTE_BATCH_SIZE = 50
_liquidity_cache = {}
_SHARE_UNIT_MULTIPLIERS = {'shares': 1, '10k_shares': 10_000}


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


def _load_json_object(path):
    try:
        with path.open('r', encoding='utf-8') as source_file:
            value = json.load(source_file)
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning('[LOF] unable to load %s: %s', path.name, exc)
        return {}


def _load_theme_taxonomy():
    return _load_json_object(_THEME_TAXONOMY_FILE)


def _load_daily_subscription_records():
    return _load_json_object(_DAILY_SUBSCRIPTIONS_FILE).get('records') or []


def _derive_hot_direction(items, taxonomy=None, now=None):
    """Select the positive-premium theme with the highest turnover-weighted premium."""
    taxonomy = taxonomy if taxonomy is not None else _load_theme_taxonomy()
    classifications = taxonomy.get('funds') or {}
    themes = {}
    unclassified_count = 0
    quote_dates = []
    for item in items:
        code = str(item.get('代码') or '')
        classification = classifications.get(code) or {}
        theme = str(classification.get('theme') or '').strip()
        basis = str(classification.get('basis') or '').strip()
        premium = safe_float(item.get('溢价率'))
        turnover = safe_float(item.get('成交额'))
        if not item.get('报价有效') or premium <= 0 or turnover <= 0:
            continue
        quote_time = _parse_iso(item.get('行情时间'))
        if quote_time:
            quote_dates.append(quote_time.date())
        if not theme:
            unclassified_count += 1
            continue
        stats = themes.setdefault(theme, {
            'premium_turnover': 0.0,
            'turnover': 0.0,
            'sample_count': 0,
            'bases': set(),
            'constituents': [],
        })
        stats['premium_turnover'] += premium * turnover
        stats['turnover'] += turnover
        stats['sample_count'] += 1
        if basis:
            stats['bases'].add(basis)
        stats['constituents'].append({
            'code': code,
            'name': str(item.get('名称') or '').strip(),
            'basis': basis,
            'premium': round(premium, 2),
            'turnover_yuan': round(turnover, 2),
        })

    candidates = []
    for name, stats in themes.items():
        if stats['turnover'] <= 0:
            continue
        candidates.append({
            'name': name,
            'weighted_premium': round(stats['premium_turnover'] / stats['turnover'], 2),
            'sample_count': stats['sample_count'],
            'turnover_yuan': round(stats['turnover'], 2),
            'method': '成交额加权正溢价',
            'source': _theme_taxonomy_source(stats['bases']),
            'constituents': stats['constituents'],
        })
    retrieved_at = (now or _now()).isoformat()
    as_of = max(quote_dates).isoformat() if quote_dates else None
    if not candidates:
        return {
            'status': 'unavailable',
            'reason': '有效正溢价分类样本不足',
            'name': None,
            'weighted_premium': None,
            'sample_count': 0,
            'turnover_yuan': 0.0,
            'unclassified_count': unclassified_count,
            'constituents': [],
            'method': '成交额加权正溢价',
            'as_of': as_of,
            'source': 'LOF 主题分类表',
            'retrieved_at': retrieved_at,
        }
    result = max(candidates, key=lambda item: (item['weighted_premium'], item['turnover_yuan']))
    result['status'] = 'available'
    result['reason'] = None
    result['unclassified_count'] = unclassified_count
    result['as_of'] = as_of
    result['retrieved_at'] = retrieved_at
    return result


def _theme_taxonomy_source(bases):
    if not bases:
        return 'LOF 主题分类表'
    return f"LOF 主题分类表（{'、'.join(sorted(bases))}）"


def _daily_subscription_unavailable(reason, expected_date=None, rejected_count=0):
    return {
        'status': 'unavailable',
        'reason': reason,
        'share_date': expected_date.isoformat() if expected_date else None,
        'capital_yuan': None,
        'account_count_lower_bound': None,
        'investor_limit_lower_bound': None,
        'record_count': 0,
        'rejected_record_count': rejected_count,
    }


def _record_limit_is_valid(record, share_date):
    subject = record.get('limit_subject')
    amount = safe_float(record.get('limit_amount'))
    starts_at = _parse_iso(record.get('limit_effective_from'))
    ends_at = _parse_iso(record.get('limit_effective_to'))
    if subject not in {'account', 'investor'} or amount <= 0:
        return False
    if not record.get('limit_source_url') or record.get('all_channels_verified') is not True:
        return False
    return bool(starts_at and ends_at and starts_at.date() <= _parse_iso(share_date).date() <= ends_at.date())


def _summarize_daily_subscriptions(records, now=None):
    """Aggregate only dated, auditable positive LOF net-subscription records."""
    expected_date = _previous_trading_weekday(now)
    expected_text = expected_date.isoformat()
    day_records = [record for record in records if str(record.get('share_date') or '') == expected_text]
    if not day_records:
        return _daily_subscription_unavailable('暂无经核验的上一交易日 LOF 份额记录', expected_date)

    capital_yuan = 0.0
    account_lower_bound = 0
    investor_lower_bound = 0
    accepted_count = 0
    rejected_count = 0
    for record in day_records:
        unit_multiplier = _SHARE_UNIT_MULTIPLIERS.get(record.get('share_unit'))
        net_share_change = safe_float(record.get('net_share_change'))
        nav = safe_float(record.get('nav'))
        has_required_evidence = bool(
            record.get('fund_code')
            and record.get('share_class')
            and record.get('source_url')
            and _parse_iso(record.get('retrieved_at'))
            and record.get('non_subscription_adjustments_excluded') is True
            and str(record.get('nav_date') or '') == expected_text
        )
        if not unit_multiplier or net_share_change <= 0 or nav <= 0 or not has_required_evidence:
            rejected_count += 1
            continue

        record_capital = net_share_change * unit_multiplier * nav
        capital_yuan += record_capital
        accepted_count += 1
        if _record_limit_is_valid(record, expected_text):
            lower_bound = math.ceil(record_capital / safe_float(record['limit_amount']))
            if record['limit_subject'] == 'account':
                account_lower_bound += lower_bound
            else:
                investor_lower_bound += lower_bound

    if not accepted_count:
        return _daily_subscription_unavailable('上一交易日记录缺少单位、净值或原始公告证据', expected_date, rejected_count)
    return {
        'status': 'available',
        'reason': None,
        'share_date': expected_text,
        'capital_yuan': round(capital_yuan, 2),
        'account_count_lower_bound': account_lower_bound or None,
        'investor_limit_lower_bound': investor_lower_bound or None,
        'record_count': accepted_count,
        'rejected_record_count': rejected_count,
    }


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


def _previous_trading_weekday(now=None):
    """Return the trading weekday immediately before the current calendar day."""
    current = (now or _now()).date() - timedelta(days=1)
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

    # Persist only normalized valid observations; missing fields are never backfilled.
    try:
        from services.lof_detail import record_observations
        from services.normalizer import normalize_lof_list

        record_observations(normalize_lof_list(result))
    except Exception as exc:
        logger.warning('[LOF] observation persistence failed: %s', exc)

    return result


def get_lof_opportunities():
    """Compatibility endpoint returning positive-premium LOFs, never ETFs or discounts."""
    items = [item for item in get_lof_list() if item['溢价率'] > 0]
    items.sort(key=lambda item: item['溢价率'], reverse=True)
    return {'premium': items, 'discount': []}


def get_lof_market_summary():
    items = get_lof_list()
    premiums = [item['溢价率'] for item in items]
    daily_subscription = _summarize_daily_subscriptions(_load_daily_subscription_records())
    return {
        'count': len(items),
        'positive_count': sum(1 for premium in premiums if premium > 0),
        'valid_quote_count': sum(1 for item in items if item['报价有效']),
        'verified_path_count': sum(1 for item in items if item['交易路径已验证']),
        'top_premium': round(max(premiums), 2) if premiums else 0,
        'premium_avg': round(sum(premiums) / len(premiums), 2) if premiums else 0,
        'hot_direction': _derive_hot_direction(items),
        'daily_subscription': daily_subscription,
    }
