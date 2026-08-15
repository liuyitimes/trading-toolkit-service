# -*- coding: utf-8 -*-
"""财经日历：新股申购/上市 + 可转债申购（东财数据中心报表）。

首页日历展示的事件来源。新股来自 RPTA_APP_IPOAPPLY（含未来申购与上市
安排），可转债来自 RPT_BOND_CB_LIST 中未上市债券的申购日期。事件按日期
排序输出，缺失字段保持为空而不是伪造。
"""

import logging
from datetime import datetime, timedelta, timezone

from services.http_client import em_get

logger = logging.getLogger('trading_toolkit')

_CST = timezone(timedelta(hours=8))
_DATACENTER_URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'
_HORIZON_DAYS = 30


def _parse_date(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:19], fmt).date()
        except ValueError:
            continue
    return None


def _fetch_ipo_rows():
    """最近的新股发行安排（按申购日倒序，覆盖未来窗口）。"""
    params = {
        'reportName': 'RPTA_APP_IPOAPPLY',
        'columns': 'ALL',
        'pageNumber': 1,
        'pageSize': 200,
        'sortColumns': 'APPLY_DATE',
        'sortTypes': '-1',
    }
    try:
        resp = em_get(_DATACENTER_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        payload = resp.json()
        return (payload.get('result') or {}).get('data') or []
    except Exception as exc:
        logger.warning('[Calendar] IPO rows fetch failed: %s', exc)
        return []


def _fetch_pending_bonds():
    """未上市可转债（东财转债列表，申购日期决定申购事件）。"""
    params = {
        'reportName': 'RPT_BOND_CB_LIST',
        'columns': 'ALL',
        'source': 'WEB',
        'client': 'WEB',
        'pageSize': '500',
        'sortColumns': 'PUBLIC_START_DATE',
        'sortTypes': '-1',
    }
    try:
        resp = em_get(_DATACENTER_URL, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        payload = resp.json()
        return (payload.get('result') or {}).get('data') or []
    except Exception as exc:
        logger.warning('[Calendar] pending bond rows fetch failed: %s', exc)
        return []


def get_market_calendar(now=None, horizon_days=_HORIZON_DAYS):
    """聚合未来窗口内的新股申购/上市与可转债申购事件。"""
    now = now or datetime.now(_CST)
    end = now.date() + timedelta(days=horizon_days)
    events = []

    for row in _fetch_ipo_rows():
        code = str(row.get('SECURITY_CODE') or '').strip()
        name = str(row.get('SECURITY_NAME') or '').strip()
        if not code or not name:
            continue
        apply_date = _parse_date(row.get('APPLY_DATE'))
        listing_date = _parse_date(row.get('LISTING_DATE'))
        if apply_date and now.date() <= apply_date <= end:
            events.append({
                'date': apply_date.isoformat(),
                'type': 'ipo_apply',
                'name': name,
                'code': code,
                'note': '新股申购',
            })
        if listing_date and now.date() <= listing_date <= end:
            events.append({
                'date': listing_date.isoformat(),
                'type': 'ipo_listing',
                'name': name,
                'code': code,
                'note': '新股上市',
            })

    for bond in _fetch_pending_bonds():
        if bond.get('LISTING_DATE'):
            continue
        apply_date = _parse_date(bond.get('PUBLIC_START_DATE'))
        name = str(bond.get('SECURITY_NAME_ABBR') or bond.get('BOND_NAME') or '').strip()
        if not apply_date or not name or not (now.date() <= apply_date <= end):
            continue
        events.append({
            'date': apply_date.isoformat(),
            'type': 'cb_apply',
            'name': name,
            'code': str(bond.get('SECURITY_CODE') or bond.get('BOND_CODE') or ''),
            'note': '可转债申购',
        })

    events.sort(key=lambda event: (event['date'], event['type']))
    return {
        'events': events,
        'horizon_days': horizon_days,
        'generated_at': now.isoformat(),
    }
