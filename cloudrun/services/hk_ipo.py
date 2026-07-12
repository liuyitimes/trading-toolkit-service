# -*- coding: utf-8 -*-
"""Hong Kong IPO observation data backed by HKEXnews disclosures.

Public HKEX data can establish that an offering document or allotment result
exists. It cannot establish a user's broker cutoff, account eligibility,
available HKD, financing approval or personal allocation. Those remain account
checks, so every public-only record is an observation rather than a trade
instruction.
"""

import io
import json
import logging
import re
from datetime import date, datetime, timedelta, timezone

import pdfplumber

from services.http_client import hkex_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

_HKT = timezone(timedelta(hours=8))
_HKEX_SEARCH_URL = 'https://www1.hkexnews.hk/search/titleSearchServlet.do'
_HKEX_FILE_HOST = 'https://www1.hkexnews.hk'
_HKEX_MARKETS = ('SEHK', 'GEM')
_OFFER_DOCUMENT_MARKER = 'listing documents - [offer for subscription]'
_ALLOTMENT_MARKER = 'allotment results'
_SEARCH_TITLES = ('GLOBAL OFFERING', 'ALLOTMENT RESULTS')
_DISCOVERY_WINDOW_DAYS = 30
_MAX_PDF_PAGES = 8


def _now():
    return datetime.now(_HKT)


def _parse_hkex_datetime(value):
    try:
        return datetime.strptime(str(value), '%d/%m/%Y %H:%M').replace(tzinfo=_HKT)
    except (TypeError, ValueError):
        return None


def _format_datetime(value):
    parsed = _parse_hkex_datetime(value)
    return parsed.isoformat() if parsed else None


def _parse_date_text(value):
    cleaned = re.sub(r'\s+', ' ', str(value or '')).strip()
    try:
        return datetime.strptime(cleaned, '%A, %B %d, %Y').date().isoformat()
    except ValueError:
        return None


def _is_offer_document(record):
    return (
        str(record.get('FILE_TYPE')).upper() == 'PDF'
        and _OFFER_DOCUMENT_MARKER in str(record.get('LONG_TEXT')).lower()
        and str(record.get('STOCK_CODE') or '').strip().isdigit()
    )


def _is_allotment_result(record):
    return (
        str(record.get('FILE_TYPE')).upper() == 'PDF'
        and _ALLOTMENT_MARKER in str(record.get('LONG_TEXT')).lower()
        and str(record.get('STOCK_CODE') or '').strip().isdigit()
    )


def _file_url(record):
    link = str(record.get('FILE_LINK') or '').strip()
    if not link:
        return None
    return link if link.startswith('http') else f'{_HKEX_FILE_HOST}{link}'


def _fetch_title_records(title, market, now=None):
    current = now or _now()
    start = (current - timedelta(days=_DISCOVERY_WINDOW_DAYS)).strftime('%Y%m%d')
    end = current.strftime('%Y%m%d')
    params = {
        'sortDir': 0,
        'sortByOptions': 'DateTime',
        'category': 0,
        'market': market,
        'stockId': '',
        'documentType': '',
        'fromDate': start,
        'toDate': end,
        'title': title,
        'searchType': 0,
        't1code': '',
        't2Gcode': '',
        't2code': '',
        'rowRange': 100,
        'lang': 'E',
    }
    try:
        response = hkex_get(_HKEX_SEARCH_URL, params=params, timeout=20)
        if response.status_code != 200:
            logger.warning('[HkIpo] HKEXnews search %s/%s HTTP %s', market, title, response.status_code)
            return []
        data = response.json()
        raw = data.get('result') or []
        return json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning('[HkIpo] HKEXnews malformed search response: %s', exc)
        return []
    except Exception as exc:
        logger.warning('[HkIpo] HKEXnews search %s/%s failed: %s', market, title, exc)
        return []


def _fetch_disclosures(now=None):
    records = []
    for market in _HKEX_MARKETS:
        for title in _SEARCH_TITLES:
            records.extend(_fetch_title_records(title, market, now))
    return records


def _base_item(code, record):
    return {
        'code': str(code).zfill(5),
        'name': str(record.get('STOCK_NAME') or '').strip(),
        'source_market': '港股',
        'strategy_status': 'observation',
        'source_name': 'HKEXnews',
        'offer_document_url': None,
        'offer_published_at': None,
        'result_document_url': None,
        'result_published_at': None,
        'status': 'observation',
        'status_reason': '仅有公开披露，尚未核验券商渠道、账户资格、资金和截止时间',
        'price_low_hkd': None,
        'price_high_hkd': None,
        'final_price_hkd': None,
        'board_lot_shares': None,
        'offer_open_date': None,
        'offer_close_date': None,
        'expected_listing_date': None,
        'document_parse_status': 'not_requested',
    }


def _merge_disclosures(records):
    items = {}
    for record in records:
        code = str(record.get('STOCK_CODE') or '').strip()
        if not code.isdigit():
            continue
        if not (_is_offer_document(record) or _is_allotment_result(record)):
            continue
        item = items.setdefault(code, _base_item(code, record))
        if not item['name']:
            item['name'] = str(record.get('STOCK_NAME') or '').strip()
        published_at = _format_datetime(record.get('DATE_TIME'))
        if _is_offer_document(record):
            if not item['offer_published_at'] or published_at > item['offer_published_at']:
                item['offer_document_url'] = _file_url(record)
                item['offer_published_at'] = published_at
        if _is_allotment_result(record):
            if not item['result_published_at'] or published_at > item['result_published_at']:
                item['result_document_url'] = _file_url(record)
                item['result_published_at'] = published_at

    merged = []
    for item in items.values():
        if item['result_document_url']:
            item['status'] = 'result_published'
            item['status_reason'] = '交易所已披露配发结果；个人获配数量仍须以券商回执核验'
        elif item['offer_document_url']:
            item['status'] = 'account_review'
            item['status_reason'] = '已发现官方发售文件；需核验券商渠道、实际截止和可用资金'
        merged.append(item)
    merged.sort(
        key=lambda item: item['result_published_at'] or item['offer_published_at'] or '',
        reverse=True,
    )
    return merged


def _fetch_pdf_text(url):
    if not url:
        return ''
    try:
        response = hkex_get(url, timeout=30)
        if response.status_code != 200:
            return ''
        with pdfplumber.open(io.BytesIO(response.content)) as pdf:
            return '\n'.join(
                page.extract_text() or ''
                for page in pdf.pages[:_MAX_PDF_PAGES]
            )
    except Exception as exc:
        logger.warning('[HkIpo] HKEX PDF parse failed for %s: %s', url, exc)
        return ''


def _first_number(text, pattern):
    match = re.search(pattern, text, re.IGNORECASE)
    return safe_float(match.group(1).replace(',', '').rstrip('.'), None) if match else None


def _extract_offer_fields(text):
    compact = re.sub(r'\s+', '', text or '')
    readable = re.sub(r'\.{2,}', ' ', text or '')
    high = _first_number(compact, r'MaximumOfferPrice:HK\$([\d,.]+)')
    low = _first_number(compact, r'notlessthanHK\$([\d,.]+)')
    board_lot_match = re.search(
        r'minimumof([\d,]+)HongKongOfferShares',
        compact,
        re.IGNORECASE,
    )
    board_lot = int(board_lot_match.group(1).replace(',', '')) if board_lot_match else None

    open_match = re.search(
        r'Hong\s*Kong\s*Public\s*Offering\s*commences.*?on\s*'
        r'([A-Z][a-z]+,\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
        readable,
        re.IGNORECASE | re.DOTALL,
    )
    close_match = re.search(
        r'Application\s*lists\s*close.*?on\s*'
        r'([A-Z][a-z]+,\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
        readable,
        re.IGNORECASE | re.DOTALL,
    )
    listing_match = re.search(
        r'Dealings\s*in\s*the.*?expected\s*to\s*commence\s*at.*?'
        r'([A-Z][a-z]+,\s*[A-Z][a-z]+\s+\d{1,2},\s+\d{4})',
        readable,
        re.IGNORECASE | re.DOTALL,
    )
    return {
        'price_low_hkd': low,
        'price_high_hkd': high,
        'board_lot_shares': board_lot,
        'offer_open_date': _parse_date_text(open_match.group(1)) if open_match else None,
        'offer_close_date': _parse_date_text(close_match.group(1)) if close_match else None,
        'expected_listing_date': _parse_date_text(listing_match.group(1)) if listing_match else None,
    }


def _extract_result_fields(text):
    compact = re.sub(r'\s+', '', text or '')
    final_price = _first_number(
        compact,
        r'(?:final)?OfferPrice(?:hasbeen)?(?:fixedat|is)HK\$([\d,.]+)',
    )
    if final_price is None:
        final_price = _first_number(compact, r'finalOfferPrice.*?HK\$([\d,.]+)')
    return {'final_price_hkd': final_price}


def _enrich_item_from_documents(item):
    enriched = dict(item)
    offer_text = _fetch_pdf_text(item.get('offer_document_url'))
    result_text = _fetch_pdf_text(item.get('result_document_url'))
    if offer_text:
        enriched.update(_extract_offer_fields(offer_text))
    if result_text:
        enriched.update(_extract_result_fields(result_text))
    enriched['document_parse_status'] = 'parsed' if offer_text or result_text else 'unavailable'
    return enriched


def _classify_status(item, today=None):
    """Classify only disclosure-backed public states, never personal eligibility."""
    if item.get('result_document_url'):
        return 'result_published'
    if item.get('offer_document_url'):
        return 'account_review'
    return 'observation'


def get_hk_ipo_list():
    """Return recent Hong Kong IPO disclosures from HKEXnews."""
    return _merge_disclosures(_fetch_disclosures())


def get_hk_ipo_upcoming():
    """Return only offering windows proved open by the official PDF.

    Public data still cannot promote an item to executable: the caller must
    separately validate broker channel, deadline and account funds.
    """
    today = _now().date()
    upcoming = []
    for item in get_hk_ipo_list():
        if item['status'] != 'account_review':
            continue
        enriched = _enrich_item_from_documents(item)
        try:
            opens = date.fromisoformat(enriched['offer_open_date'])
            closes = date.fromisoformat(enriched['offer_close_date'])
        except (TypeError, ValueError):
            continue
        if opens <= today <= closes:
            enriched['status'] = 'account_review'
            upcoming.append(enriched)
    return upcoming


def get_hk_ipo_detail(code):
    """Return one IPO with official-PDF fields when available."""
    normalized = str(code or '').zfill(5)
    for item in get_hk_ipo_list():
        if item['code'] == normalized:
            return _enrich_item_from_documents(item)
    return None


def get_hk_ipo_summary():
    """Summarise disclosure-backed Hong Kong IPO observation states."""
    items = get_hk_ipo_list()
    return {
        'total': len(items),
        'account_review_count': sum(item['status'] == 'account_review' for item in items),
        'result_published_count': sum(item['status'] == 'result_published' for item in items),
        'open_window_count': len(get_hk_ipo_upcoming()),
        'source_market': '港股',
        'source_name': 'HKEXnews',
    }
