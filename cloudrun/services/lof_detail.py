"""Decision-grade LOF detail data built from persisted valid observations."""

import json
import os
import statistics
import threading
from datetime import date
from pathlib import Path

from services.lof_fund import get_lof_list
from services.normalizer import normalize_lof_list


_LOCK = threading.RLock()
_PURCHASE_FEE_PCT = 0.15
_SELL_COMMISSION_PCT = 0.05
_HOLDINGS_MAX_AGE_DAYS = 120


def _data_dir():
    configured = os.environ.get('LOF_DETAIL_DATA_DIR', '').strip()
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / 'data' / 'lof_detail'


def _observations_path():
    return _data_dir() / 'observations.json'


def _holdings_path():
    return _data_dir() / 'holdings.json'


def _load_json(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return default


def _save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def _observation_from_item(item):
    quote_at = str(item.get('quote_at') or '')
    return {
        'observed_at': quote_at,
        'session_date': quote_at[:10],
        'price': float(item['price']),
        'valuation': float(item['valuation']),
        'premium': float(item['premium']),
        'amount': float(item.get('amount') or 0),
        'volume': float(item.get('volume') or 0),
        'source': 'Tencent quote with latest unit NAV',
    }


def record_observations(items):
    """Persist one valid quote observation per LOF per trading session."""
    with _LOCK:
        data = _load_json(_observations_path(), {'version': 1, 'items': {}})
        records = data.setdefault('items', {})
        for item in items:
            if not item.get('valid_quote') or not item.get('code') or not item.get('quote_at'):
                continue
            observation = _observation_from_item(item)
            if not observation['session_date']:
                continue
            history = records.setdefault(str(item['code']), [])
            history = [row for row in history if row.get('session_date') != observation['session_date']]
            history.append(observation)
            records[str(item['code'])] = sorted(history, key=lambda row: row['observed_at'])[-240:]
        _save_json(_observations_path(), data)


def get_observations(code):
    data = _load_json(_observations_path(), {'items': {}})
    return list(data.get('items', {}).get(str(code), []))


def _window(history, count):
    samples = history[-count:]
    if len(samples) < count:
        return {'available': False, 'window_sessions': count, 'sample_count': len(samples)}

    premiums = [row['premium'] for row in samples]
    amounts = [row['amount'] for row in samples]
    return {
        'available': True,
        'window_sessions': count,
        'sample_count': len(samples),
        'premium_min_pct': min(premiums),
        'premium_max_pct': max(premiums),
        'premium_range_pct': round(max(premiums) - min(premiums), 4),
        'average_turnover': round(sum(amounts) / len(amounts), 4),
    }


def _consecutive_positive_sessions(history):
    count = 0
    for row in reversed(history):
        if row.get('premium', 0) <= 0:
            break
        count += 1
    return count


def _return_std(values):
    returns = []
    for previous, current in zip(values, values[1:]):
        if previous > 0:
            returns.append((current / previous - 1) * 100)
    return round(statistics.pstdev(returns), 4) if len(returns) >= 2 else None


def _volatility(history, count):
    samples = history[-count:]
    if len(samples) < count:
        return {'available': False, 'window_sessions': count, 'sample_count': len(samples)}

    prices = [row['price'] for row in samples]
    navs = [row['valuation'] for row in samples]
    premiums = [row['premium'] for row in samples]
    return {
        'available': True,
        'window_sessions': count,
        'sample_count': len(samples),
        'price_return_std_pct': _return_std(prices),
        'nav_return_std_pct': _return_std(navs),
        'premium_std_pct': round(statistics.pstdev(premiums), 4),
        'premium_range_pct': round(max(premiums) - min(premiums), 4),
    }


def _holdings_for(code, today=None):
    data = _load_json(_holdings_path(), {'items': {}})
    item = data.get('items', {}).get(str(code))
    source = item.get('source') if item else None
    if not item or not item.get('as_of') or not isinstance(source, dict):
        return {
            'available': False,
            'status': 'unavailable',
            'reason': 'No verified fund portfolio disclosure is available.',
            'top_holdings': [],
        }
    if not source.get('url') or not source.get('retrieved_at') or source.get('kind') not in {
        'manager_report', 'fund_quarterly_report', 'fund_annual_report',
    }:
        return {
            'available': False,
            'status': 'unavailable',
            'reason': 'The holdings disclosure lacks verifiable source metadata.',
            'top_holdings': [],
        }
    try:
        disclosure_date = date.fromisoformat(str(item['as_of'])[:10])
    except ValueError:
        return {
            'available': False,
            'status': 'unavailable',
            'reason': 'The holdings disclosure date is invalid.',
            'top_holdings': [],
        }
    age_days = ((today or date.today()) - disclosure_date).days
    if age_days > _HOLDINGS_MAX_AGE_DAYS:
        return {
            'available': False,
            'status': 'stale',
            'reason': f'The verified holdings disclosure is {age_days} days old.',
            'as_of': item['as_of'],
            'source': source,
            'top_holdings': [],
        }
    return {
        'available': True,
        'status': 'available',
        'as_of': item['as_of'],
        'source': source,
        'concentration_pct': item.get('concentration_pct'),
        'top_holdings': item.get('top_holdings', []),
    }


def build_lof_detail(current, history, holdings):
    """Build the documented detail contract from observed and verified inputs."""
    history = sorted(history, key=lambda row: row.get('observed_at', ''))
    five_session = _window(history, 5)
    twenty_session = _window(history, 20)
    verified_path = bool(current.get('trade_path_verified'))
    valid_quote = bool(current.get('valid_quote'))
    executable_candidate = valid_quote and verified_path and bool(current.get('subscription_open'))

    return {
        'code': current['code'],
        'strategy_status': 'executable_candidate' if executable_candidate else 'observation',
        'instrument': {
            'code': current['code'],
            'name': current['name'],
            'exchange': current.get('exchange'),
            'price': current.get('price'),
            'valuation': current.get('valuation'),
            'quote_at': current.get('quote_at'),
            'nav_date': current.get('nav_date'),
            'nav_source': current.get('nav_source'),
            'valid_quote': valid_quote,
        },
        'execution': {
            'subscription_open': bool(current.get('subscription_open')),
            'subscription_limit': current.get('subscription_limit'),
            'custody_transfer': bool(current.get('custody_transfer')),
            'expected_sell_date': current.get('expected_sell_date'),
            'trade_path_verified': verified_path,
            'evidence': current.get('verification_evidence') or {},
        },
        'premium': {
            'gross_pct': current['premium'],
            'net_assumption_pct': round(current['premium'] - _PURCHASE_FEE_PCT - _SELL_COMMISSION_PCT, 4),
            'cost_assumptions': {
                'purchase_fee_pct': _PURCHASE_FEE_PCT,
                'sell_commission_pct': _SELL_COMMISSION_PCT,
                'account_specific': False,
            },
            'persistence': {
                'consecutive_positive_sessions': _consecutive_positive_sessions(history),
                'five_session': five_session,
                'twenty_session': twenty_session,
            },
            'observations': history[-20:],
        },
        'liquidity': {
            'current_turnover': current.get('amount'),
            'current_volume': current.get('volume'),
            'five_session': five_session,
            'twenty_session': twenty_session,
        },
        'holdings': holdings or {
            'available': False,
            'status': 'unavailable',
            'reason': 'No verified fund portfolio disclosure is available.',
            'top_holdings': [],
        },
        'volatility': {
            'five_session': _volatility(history, 5),
            'twenty_session': _volatility(history, 20),
        },
        'provenance': {
            'history_source': 'persisted valid LOF quote observations',
            'history_sample_count': len(history),
            'holdings_kind': 'fund_portfolio_not_user_position',
        },
    }


def get_lof_detail(code):
    """Fetch current LOF data, persist it when valid, and build a detail view."""
    items = normalize_lof_list(get_lof_list())
    record_observations(items)
    current = next((item for item in items if item['code'] == str(code)), None)
    if current is None:
        return None
    return build_lof_detail(current, get_observations(code), _holdings_for(code))
