# -*- coding: utf-8 -*-
"""可审计的 LOF 场内申赎规则库与采集任务。"""

import hashlib
import io
import json
import re
import zipfile
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urljoin
from xml.etree import ElementTree

import requests
from sqlalchemy import select

from models.lof_execution import (
    LofExecutionEvidence,
    LofExecutionFund,
    LofExecutionJob,
    LofExecutionRule,
)
from models.lof_premium import TradingCalendar


_CST = timezone(timedelta(hours=8))
_SSE_GUIDE_URL = 'https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20250519_10779392.shtml'
_SSE_GUIDE_ID = 'sse-lof-guide-2019'
_SSE_GUIDE_TITLE = '上海证券交易所上市开放式基金业务指引（2019年修订）'
_SSE_GUIDE_EFFECTIVE = date(2019, 2, 15)
_EM_NAV_URL = 'https://api.fund.eastmoney.com/f10/lsjz'
_SZSE_FUND_DISCLOSURE_URL = 'https://www.szse.cn/disclosure/fund/'

_SOURCE_PRIORITIES = {
    'special_announcement': 100,
    'manager_announcement': 100,
    'fund_contract': 80,
    'prospectus': 80,
    'manager_product_page': 60,
    'sse_rule': 10,
    'csrc_rule': 10,
}
_RULE_FIELDS = {
    'subscription_confirmation',
    'redemption_payment',
    'subscription_minimum',
    'redemption_minimum',
}


def _now():
    return datetime.now(_CST)


def _exchange_name(value):
    return 'sh' if str(value).strip().lower() in {'1', '沪', 'sh'} else 'sz'


def _source_payload(evidence):
    if evidence is None:
        return None
    return {
        'title': evidence.source_title,
        'url': evidence.source_url,
        'effective_date': evidence.effective_from.isoformat() if evidence.effective_from else None,
        'verified_at': evidence.verified_at.replace(tzinfo=_CST).isoformat() if evidence.verified_at else None,
    }


def _unavailable(reason=None):
    result = {'status': 'unavailable'}
    if reason:
        result['reason'] = reason
    return result


def _fund_identity(row):
    """Stable rule-library identity, independent of the quote-provider order."""
    code = str(
        row.get('f12') or row.get('fund_code') or row.get('code') or row.get('代码') or ''
    ).strip()
    exchange = _exchange_name(row.get('f13') or row.get('exchange') or row.get('交易所'))
    share_class = str(row.get('share_class') or row.get('份额类别') or 'listed').strip() or 'listed'
    return code, exchange, share_class


def execution_rule_key(code, exchange, share_class='listed'):
    """Map key used by quote consumers that know the complete fund identity."""
    return f'{code}|{_exchange_name(exchange)}|{share_class or "listed"}'


def _load_job_cursor(job):
    if not job.cursor:
        return {}
    try:
        value = json.loads(job.cursor)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _save_job_cursor(db, job, **values):
    job.cursor = json.dumps(values, ensure_ascii=False, sort_keys=True)
    db.commit()


def _find_or_create_job(db, job_type):
    job = db.execute(select(LofExecutionJob).where(LofExecutionJob.job_type == job_type)).scalar_one_or_none()
    if job is None:
        job = LofExecutionJob(job_type=job_type)
        db.add(job)
        db.flush()
    return job


def _upsert_fund(db, row):
    code, exchange, share_class = _fund_identity(row)
    if not code:
        return None
    fund = db.execute(select(LofExecutionFund).where(
        LofExecutionFund.fund_code == code,
        LofExecutionFund.exchange == exchange,
        LofExecutionFund.share_class == share_class,
    )).scalar_one_or_none()
    if fund is None:
        fund = LofExecutionFund(fund_code=code, exchange=exchange)
        db.add(fund)
    fund.exchange = exchange
    fund.fund_name = str(row.get('f14') or row.get('name') or row.get('名称') or fund.fund_name or '').strip() or None
    fund.share_class = share_class
    return fund


def _docx_text(content):
    """提取 DOCX 正文，不使用模糊语义或模型推断。"""
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        document = archive.read('word/document.xml')
    root = ElementTree.fromstring(document)
    return re.sub(r'\s+', ' ', ''.join(root.itertext())).strip()


def _section(text, article, next_article):
    start = text.find(article)
    if start < 0:
        raise ValueError(f'上交所 LOF 指引缺少{article}')
    end = text.find(next_article, start + len(article))
    return text[start:end if end >= 0 else len(text)]


def _parse_sse_guide_rules(text):
    """从指引第 39、46 条确定性提取可展示的场内字段。"""
    article_39 = _section(text, '第三十九条', '第四十条')
    article_46 = _section(text, '第四十六条', '第四十七条')
    if '场内证券经营机构' not in article_39 or '场内证券经营机构' not in article_46:
        raise ValueError('上交所 LOF 指引未明确场内渠道')
    minimum = re.search(r'申购金额[^。；;]*?不低于\s*(\d+)\s*元', article_39)
    confirmation = re.search(r'T\s*[＋+]\s*(\d+)\s*日[^。；;]*?场内申购确认结果', article_46)
    if not minimum or not confirmation:
        raise ValueError('上交所 LOF 指引未找到可确定解析的申购规则')
    if confirmation.group(1) != '1':
        raise ValueError('上交所 LOF 指引的申购确认周期不符合预期')
    return {
        'subscription_confirmation': 'T+1',
        'subscription_minimum': f'{minimum.group(1)} 元',
        'subscription_minimum_value': float(minimum.group(1)),
        'excerpt': f'{article_39[:180]} {article_46[:220]}',
    }


def _official_sse_evidence(db, fetcher=requests.get):
    """下载并确定性解析现行上交所指引附件，返回可审计证据与规则。"""
    evidence = db.execute(
        select(LofExecutionEvidence).where(
            LofExecutionEvidence.source_kind == 'sse_rule',
            LofExecutionEvidence.source_identifier == _SSE_GUIDE_ID,
        )
    ).scalar_one_or_none()
    response = fetcher(_SSE_GUIDE_URL, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
    response.raise_for_status()
    page_bytes = getattr(response, 'content', b'') or b''
    page_text = page_bytes.decode('utf-8', 'replace') if page_bytes else response.text
    if '上市开放式基金业务指引' not in page_text or '现行有效' not in page_text:
        raise ValueError('上交所 LOF 指引未确认现行有效')
    docx_match = re.search(r'([\w./-]+\.docx)(?:["\'?#]|$)', page_text, re.IGNORECASE)
    if not docx_match:
        raise ValueError('上交所 LOF 指引页面未提供 DOCX 附件')
    document_url = urljoin(_SSE_GUIDE_URL, docx_match.group(1))
    document_response = fetcher(document_url, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
    document_response.raise_for_status()
    parsed = _parse_sse_guide_rules(_docx_text(document_response.content))
    digest = hashlib.sha256(document_response.content).hexdigest()
    if evidence is None:
        evidence = LofExecutionEvidence(
            source_kind='sse_rule',
            source_identifier=_SSE_GUIDE_ID,
            source_title=_SSE_GUIDE_TITLE,
            source_url=document_url,
            applies_to='sh_all_listed_lof',
            published_at=_SSE_GUIDE_EFFECTIVE,
            effective_from=_SSE_GUIDE_EFFECTIVE,
            excerpt=parsed['excerpt'],
        )
        db.add(evidence)
    evidence.source_url = document_url
    evidence.excerpt = parsed['excerpt']
    evidence.content_hash = digest
    evidence.verified_at = _now().replace(tzinfo=None)
    db.flush()
    return evidence, parsed


def _upsert_generic_rule(db, evidence, field_key, value_text=None, numeric_value=None, unit=None):
    rule = db.execute(
        select(LofExecutionRule).where(
            LofExecutionRule.fund_id.is_(None),
            LofExecutionRule.exchange == 'sh',
            LofExecutionRule.share_class == 'listed',
            LofExecutionRule.field_key == field_key,
            LofExecutionRule.evidence_id == evidence.id,
        )
    ).scalar_one_or_none()
    if rule is None:
        rule = LofExecutionRule(
            exchange='sh', share_class='listed', field_key=field_key, evidence_id=evidence.id,
        )
        db.add(rule)
    rule.value_text = value_text
    rule.numeric_value = numeric_value
    rule.unit = unit
    rule.status = 'verified'
    rule.reason = None
    rule.source_priority = 10
    rule.effective_from = _SSE_GUIDE_EFFECTIVE
    return rule


def derive_trading_timing(db, request_date, completion_date):
    """以已导入 A 股交易日历计算同一证据的 T+n。"""
    if completion_date < request_date:
        raise ValueError('完成日期早于申请日期')
    request_day = db.execute(select(TradingCalendar).where(
        TradingCalendar.calendar_date == request_date,
    )).scalar_one_or_none()
    completion_day = db.execute(select(TradingCalendar).where(
        TradingCalendar.calendar_date == completion_date,
    )).scalar_one_or_none()
    if not request_day or not request_day.is_trading_day or not completion_day or not completion_day.is_trading_day:
        raise ValueError('日期未由 A 股交易日历确认')
    count = db.execute(select(TradingCalendar).where(
        TradingCalendar.calendar_date > request_date,
        TradingCalendar.calendar_date <= completion_date,
        TradingCalendar.is_trading_day.is_(True),
    )).scalars().all()
    return f'T+{len(count)}'


def upsert_fund_rule_version(db, fund, evidence, field_key, value_text, effective_from,
                             source_priority, numeric_value=None, unit=None,
                             replaces_previous=False):
    """写入专项规则；仅凭明确替代证据关闭同级旧版本。"""
    if field_key not in _RULE_FIELDS:
        raise ValueError(f'不支持的 LOF 场内规则字段：{field_key}')
    if not effective_from:
        raise ValueError('专项规则必须提供生效日期')
    existing = db.execute(select(LofExecutionRule).where(
        LofExecutionRule.fund_id == fund.id,
        LofExecutionRule.exchange == fund.exchange,
        LofExecutionRule.share_class == fund.share_class,
        LofExecutionRule.field_key == field_key,
        LofExecutionRule.evidence_id == evidence.id,
    )).scalar_one_or_none()
    if existing is not None:
        existing.value_text = value_text
        existing.numeric_value = numeric_value
        existing.unit = unit
        existing.effective_from = effective_from
        existing.source_priority = source_priority
        existing.status = 'verified'
        existing.reason = None
        db.flush()
        return existing
    if replaces_previous:
        old_rules = db.execute(select(LofExecutionRule).where(
            LofExecutionRule.fund_id == fund.id,
            LofExecutionRule.exchange == fund.exchange,
            LofExecutionRule.share_class == fund.share_class,
            LofExecutionRule.field_key == field_key,
            LofExecutionRule.source_priority == source_priority,
            LofExecutionRule.effective_from < effective_from,
            (LofExecutionRule.effective_to.is_(None)) | (LofExecutionRule.effective_to >= effective_from),
        )).scalars().all()
        for old_rule in old_rules:
            old_rule.effective_to = effective_from - timedelta(days=1)
    rule = LofExecutionRule(
        fund_id=fund.id, exchange=fund.exchange, share_class=fund.share_class,
        field_key=field_key, value_text=value_text, numeric_value=numeric_value, unit=unit,
        status='verified', source_priority=source_priority, evidence_id=evidence.id,
        effective_from=effective_from,
    )
    db.add(rule)
    db.flush()
    return rule


def ingest_execution_rule_evidence(db, item):
    """Persist one externally discovered, already-auditable fund rule update.

    Discovery adapters must supply the concrete target identity, source metadata,
    an effective date and explicitly parsed fields.  This boundary intentionally
    rejects prose-only or out-of-scope material so an announcement cannot leak
    into another share class or an off-exchange rule.
    """
    source = item.get('source') or {}
    source_kind = str(source.get('kind') or '').strip()
    priority = _SOURCE_PRIORITIES.get(source_kind)
    if priority is None:
        raise ValueError('不支持或未核验的规则来源类型')
    identity = {
        'code': item.get('fund_code'),
        'exchange': item.get('exchange'),
        'share_class': item.get('share_class') or 'listed',
    }
    if not identity['code'] or not identity['exchange']:
        raise ValueError('规则证据缺少基金代码或交易所')
    if source.get('applies_to') != 'fund_code' or source.get('channel') != 'on_exchange':
        raise ValueError('规则证据必须明确适用于目标基金的场内渠道')
    if str(source.get('fund_code') or '').strip() != str(identity['code']).strip():
        raise ValueError('规则证据未明确覆盖目标基金代码')
    if _exchange_name(source.get('exchange')) != _exchange_name(identity['exchange']):
        raise ValueError('规则证据未明确覆盖目标交易所')
    if str(source.get('share_class') or 'listed').strip() != str(identity['share_class']).strip():
        raise ValueError('规则证据未明确覆盖目标份额类别')
    fund = _upsert_fund(db, identity)
    if fund is None:
        raise ValueError('规则证据缺少基金代码')
    identifier = str(source.get('identifier') or '').strip()
    title = str(source.get('title') or '').strip()
    url = str(source.get('url') or '').strip()
    effective_from = item.get('effective_from') or source.get('effective_from')
    if isinstance(effective_from, str):
        effective_from = date.fromisoformat(effective_from)
    if not identifier or not title or not url or not effective_from:
        raise ValueError('规则证据缺少可审计来源或生效日期')
    evidence = db.execute(select(LofExecutionEvidence).where(
        LofExecutionEvidence.source_kind == source_kind,
        LofExecutionEvidence.source_identifier == identifier,
    )).scalar_one_or_none()
    if evidence is None:
        evidence = LofExecutionEvidence(
            source_kind=source_kind,
            source_identifier=identifier,
            source_title=title,
            source_url=url,
            applies_to='fund_code',
        )
        db.add(evidence)
    evidence.source_title = title
    evidence.source_url = url
    evidence.applies_to = source['applies_to']
    published_at = source.get('published_at') or effective_from
    evidence.published_at = date.fromisoformat(published_at) if isinstance(published_at, str) else published_at
    evidence.effective_from = effective_from
    evidence.content_hash = source.get('content_hash') or evidence.content_hash
    evidence.excerpt = source.get('excerpt') or evidence.excerpt
    evidence.verified_at = _now().replace(tzinfo=None)
    db.flush()
    fields = item.get('fields') or {}
    if not fields:
        raise ValueError('规则证据未包含可确定解析的场内字段')
    for field_key, value in fields.items():
        if field_key not in _RULE_FIELDS:
            raise ValueError(f'不支持的 LOF 场内规则字段：{field_key}')
        if not isinstance(value, dict):
            value = {'value_text': value}
        value_text = value.get('value_text')
        excerpt = str(value.get('excerpt') or source.get('excerpt') or '').strip()
        required_terms = {
            'subscription_confirmation': ('场内', '申购', '确认'),
            'redemption_payment': ('场内', '赎回'),
            'subscription_minimum': ('场内', '申购'),
            'redemption_minimum': ('场内', '赎回'),
        }[field_key]
        if not excerpt or not all(term in excerpt for term in required_terms):
            raise ValueError(f'{field_key} 缺少包含场内字段语义的原文摘录')
        request_date = value.get('request_date')
        completion_date = value.get('completion_date')
        if request_date or completion_date:
            if not request_date or not completion_date:
                raise ValueError('日期推导 T+n 必须同时提供申请日和完成日')
            if isinstance(request_date, str):
                request_date = date.fromisoformat(request_date)
            if isinstance(completion_date, str):
                completion_date = date.fromisoformat(completion_date)
            value_text = derive_trading_timing(db, request_date, completion_date)
        if not value_text:
            raise ValueError('规则字段缺少确定值')
        if field_key.endswith(('confirmation', 'payment')) and not re.fullmatch(r'T\s*[+＋]\s*\d+', str(value_text)):
            raise ValueError('场内时效必须为明示或交易日推导的 T+n')
        if field_key.endswith('minimum') and not re.search(r'\d', str(value_text)):
            raise ValueError('最低申赎必须保留原始数值')
        upsert_fund_rule_version(
            db, fund, evidence, field_key, str(value_text), effective_from,
            priority, numeric_value=value.get('numeric_value'), unit=value.get('unit'),
            replaces_previous=bool(value.get('replaces_previous')),
        )
    fund.discovery_status = 'verified'
    fund.discovery_reason = None
    db.flush()
    return fund


def _record_discovery_attempt(db, fund, source_url, reason):
    identifier = f'discovery:{fund.fund_code}:{fund.exchange}:{fund.share_class}'
    evidence = db.execute(select(LofExecutionEvidence).where(
        LofExecutionEvidence.source_kind == 'discovery_attempt',
        LofExecutionEvidence.source_identifier == identifier,
    )).scalar_one_or_none()
    if evidence is None:
        evidence = LofExecutionEvidence(
            source_kind='discovery_attempt', source_identifier=identifier,
            source_title='LOF 场内规则检索记录', source_url=source_url,
            applies_to='fund_code', excerpt=reason,
        )
        db.add(evidence)
    evidence.verified_at = _now().replace(tzinfo=None)
    evidence.excerpt = reason


def _seed_sse_generic_rules(db, fetcher=requests.get):
    evidence, parsed = _official_sse_evidence(db, fetcher=fetcher)
    _upsert_generic_rule(db, evidence, 'subscription_confirmation', value_text=parsed['subscription_confirmation'])
    _upsert_generic_rule(
        db, evidence, 'subscription_minimum', value_text=parsed['subscription_minimum'],
        numeric_value=parsed['subscription_minimum_value'], unit='元',
    )
    db.flush()
    return evidence


def run_execution_rules_incremental(db, evidence_items, restart=False):
    """Ingest an ordered batch of newly discovered, normalized rule evidence.

    A job cursor holds the next source item so a scheduler can safely take over
    after a process interruption.  The caller owns discovery; this service owns
    validation, versioning and durable progress.
    """
    job = _find_or_create_job(db, 'rule_incremental')
    items = list(evidence_items)
    cursor = _load_job_cursor(job) if restart else {}
    next_index = int(cursor.get('next_index', 0)) if cursor else 0
    if job.status == 'running' and not restart:
        return {'acquired': False, 'reason': '任务正在运行；使用 --restart 从保存进度接管'}
    job.status = 'running'
    job.attempt_count = (job.attempt_count or 0) + 1
    job.started_at = _now().replace(tzinfo=None)
    job.completed_at = None
    job.last_error = None
    db.commit()
    for index, item in enumerate(items[next_index:], start=next_index):
        try:
            ingest_execution_rule_evidence(db, item)
            job.success_count = (job.success_count or 0) + 1
            _save_job_cursor(db, job, next_index=index + 1)
        except Exception as exc:
            db.rollback()
            job = _find_or_create_job(db, 'rule_incremental')
            job.failure_count = (job.failure_count or 0) + 1
            job.last_error = str(exc)
            job.status = 'failed'
            job.completed_at = _now().replace(tzinfo=None)
            job.cursor = json.dumps({'next_index': index}, ensure_ascii=False)
            db.commit()
            return {'acquired': False, 'error': str(exc), 'next_index': index}
    job.status = 'succeeded'
    job.completed_at = _now().replace(tzinfo=None)
    job.cursor = None
    db.commit()
    return {'acquired': True, 'success_count': job.success_count, 'failure_count': job.failure_count}


def run_execution_rules_backfill(db, universe, fetcher=requests.get, restart=False):
    """为全部当前有效 LOF 建档；只向有正式证据的字段写入规则。"""
    job = _find_or_create_job(db, 'rule_backfill')
    if job.status == 'running' and not restart:
        return {'acquired': False, 'reason': '任务正在运行；使用 --restart 从保存进度接管'}
    rows = sorted(
        (row for row in universe if _fund_identity(row)[0]),
        key=_fund_identity,
    )
    cursor = _load_job_cursor(job) if restart else {}
    last_identity = tuple(cursor['last_identity']) if cursor.get('last_identity') else None
    start_index = 0
    if last_identity:
        for index, row in enumerate(rows):
            if _fund_identity(row) == last_identity:
                start_index = index + 1
                break
    job.status = 'running'
    job.attempt_count += 1
    job.started_at = _now().replace(tzinfo=None)
    job.last_error = None
    job.completed_at = None
    if not cursor:
        job.success_count = 0
        job.failure_count = 0
    db.commit()
    try:
        _seed_sse_generic_rules(db, fetcher=fetcher)
        db.commit()
        for row in rows[start_index:]:
            fund = _upsert_fund(db, row)
            if fund is None:
                continue
            if fund.exchange == 'sh':
                fund.discovery_status = 'partial'
                fund.discovery_reason = '已应用上交所通用场内规则；基金专项规则待公告增量补充'
                _record_discovery_attempt(db, fund, _SSE_GUIDE_URL, fund.discovery_reason)
            else:
                fund.discovery_status = 'unavailable'
                fund.discovery_reason = '尚未取得满足口径的深市或基金专项场内规则证据'
                _record_discovery_attempt(db, fund, _SZSE_FUND_DISCLOSURE_URL, fund.discovery_reason)
            job.success_count += 1
            _save_job_cursor(db, job, last_identity=list(_fund_identity(row)))
        job.status = 'succeeded'
        job.completed_at = _now().replace(tzinfo=None)
        job.cursor = None
        db.commit()
        return {'acquired': True, 'fund_count': job.success_count, 'failure_count': 0}
    except Exception as exc:
        db.rollback()
        job = _find_or_create_job(db, 'rule_backfill')
        job.status = 'failed'
        job.failure_count += 1
        job.last_error = str(exc)
        job.completed_at = _now().replace(tzinfo=None)
        db.commit()
        return {'acquired': False, 'error': str(exc)}


def fetch_em_status(fund_code, getter=requests.get):
    """读取东财最新净值条目的开闭状态；仅用作当日状态，不推导时效。"""
    response = getter(
        _EM_NAV_URL,
        params={'fundCode': str(fund_code), 'pageIndex': 1, 'pageSize': 1, 'startDate': '', 'endDate': ''},
        headers={'Referer': 'https://fundf10.eastmoney.com/', 'User-Agent': 'Mozilla/5.0'},
        timeout=20,
    )
    response.raise_for_status()
    rows = (response.json().get('Data') or {}).get('LSJZList') or []
    if not rows:
        return None
    row = rows[0]
    return {
        'subscription_status': 'open' if str(row.get('SGZT') or '').strip() == '开放申购' else 'closed',
        'redemption_status': 'open' if str(row.get('SHZT') or '').strip() == '开放赎回' else 'closed',
        'source_url': _EM_NAV_URL,
    }


def run_execution_status_refresh(db, ranked_universe, getter=requests.get, top=20, restart=False, now=None):
    """只刷新启动时当前溢价前 20 的当日开闭状态。"""
    refresh_at = now or _now()
    calendar_day = db.execute(select(TradingCalendar).where(
        TradingCalendar.calendar_date == refresh_at.date(),
    )).scalar_one_or_none()
    if not calendar_day or not calendar_day.is_trading_day:
        return {'acquired': False, 'reason': '当日未由 A 股交易日历确认为交易日'}
    if (refresh_at.hour, refresh_at.minute) < (15, 0):
        return {'acquired': False, 'reason': '场内申赎状态仅在收盘后刷新'}
    job = _find_or_create_job(db, 'status_refresh')
    if job.status == 'running' and not restart:
        return {'acquired': False, 'reason': '任务正在运行；使用 --restart 从保存进度接管'}
    cursor = _load_job_cursor(job) if restart else {}
    job.status = 'running'
    job.attempt_count += 1
    job.started_at = refresh_at.replace(tzinfo=None)
    job.completed_at = None
    if cursor.get('candidates'):
        candidates = cursor['candidates']
        start_index = int(cursor.get('next_index', 0))
    else:
        candidates = sorted(
            (row for row in ranked_universe if row.get('报价有效') or row.get('valid_quote')),
            key=lambda row: float(row.get('溢价率', row.get('premium', 0)) or 0),
            reverse=True,
        )[:top]
        start_index = 0
        job.success_count = 0
        job.failure_count = 0
    db.commit()
    for index, row in enumerate(candidates[start_index:], start=start_index):
        fund = _upsert_fund(db, row)
        if fund is None:
            continue
        try:
            status = fetch_em_status(fund.fund_code, getter=getter)
            if status:
                fund.subscription_status = status['subscription_status']
                fund.redemption_status = status['redemption_status']
                fund.status_checked_at = refresh_at.replace(tzinfo=None)
                fund.status_source_url = status['source_url']
                job.success_count += 1
            else:
                job.failure_count += 1
        except Exception as exc:
            job.failure_count += 1
            job.last_error = str(exc)
        _save_job_cursor(db, job, candidates=candidates, next_index=index + 1)
    job.status = 'succeeded'
    job.completed_at = refresh_at.replace(tzinfo=None)
    job.cursor = None
    db.commit()
    return {'acquired': True, 'target_count': len(candidates), 'success_count': job.success_count, 'failure_count': job.failure_count}


def _current_rules(db, fund, today):
    rules = db.execute(
        select(LofExecutionRule, LofExecutionEvidence)
        .outerjoin(LofExecutionEvidence, LofExecutionRule.evidence_id == LofExecutionEvidence.id)
        .where(
            LofExecutionRule.exchange == fund.exchange,
            LofExecutionRule.share_class == fund.share_class,
            (LofExecutionRule.fund_id.is_(None)) | (LofExecutionRule.fund_id == fund.id),
        )
    ).all()
    grouped = {}
    for rule, evidence in rules:
        if rule.effective_from and rule.effective_from > today:
            continue
        if rule.effective_to and rule.effective_to < today:
            continue
        grouped.setdefault(rule.field_key, []).append((rule, evidence))
    resolved = {}
    for field_key, candidates in grouped.items():
        priority = max(rule.source_priority for rule, _ in candidates)
        top = [(rule, evidence) for rule, evidence in candidates if rule.source_priority == priority]
        values = {rule.value_text for rule, _ in top}
        if len(values) != 1:
            resolved[field_key] = _unavailable('同优先级规则冲突')
            continue
        rule, evidence = max(top, key=lambda item: item[0].updated_at or datetime.min)
        resolved[field_key] = {
            'status': rule.status,
            'timing_text': rule.value_text if field_key.endswith('confirmation') or field_key.endswith('payment') else None,
            'display_text': rule.value_text,
            'value': rule.numeric_value,
            'unit': rule.unit,
            'source': _source_payload(evidence),
        }
    return resolved


def resolve_execution_rules(db, codes, now=None):
    """返回列表接口所需的当前场内规则；缺失字段不伪造默认值。"""
    now = now or _now()
    today = now.date()
    requested_codes = [
        str(code.get('f12') or code.get('fund_code') or code.get('code') or code.get('代码') or '')
        if isinstance(code, dict) else str(code)
        for code in codes
    ]
    funds = db.execute(select(LofExecutionFund).where(
        LofExecutionFund.fund_code.in_(requested_codes)
    )).scalars().all()
    result = {}
    by_code = {}
    for fund in funds:
        values = _current_rules(db, fund, today)
        checked_today = bool(fund.status_checked_at and fund.status_checked_at.date() == today)
        subscription_open = checked_today and fund.subscription_status == 'open'
        payload = {
            'has_record': True,
            'subscription_status': '开放申购' if subscription_open else '待核验',
            'subscription_open': subscription_open,
            'subscription_limit': None,
            'custody_transfer': False,
            'expected_sell_date': None,
            'settlement_timing': {
                'subscription_confirmation': values.get('subscription_confirmation', _unavailable(fund.discovery_reason)),
                'redemption_payment': values.get('redemption_payment', _unavailable(fund.discovery_reason)),
            },
            'minimum_order': {
                'subscription': values.get('subscription_minimum', _unavailable(fund.discovery_reason)),
                'redemption': values.get('redemption_minimum', _unavailable(fund.discovery_reason)),
            },
            'evidence': {
                'subscription': {
                    'url': fund.status_source_url if checked_today else None,
                    'checked_at': fund.status_checked_at.replace(tzinfo=_CST).isoformat() if checked_today else None,
                    'current': checked_today,
                    'source_name': '东方财富基金状态' if checked_today else None,
                }
            },
            'manual_override_active': False,
            'trade_path_verified': False,
            'custody_transfer': False,
            'expected_sell_date': None,
        }
        result[execution_rule_key(fund.fund_code, fund.exchange, fund.share_class)] = payload
        by_code.setdefault(fund.fund_code, []).append(payload)
    for code, values in by_code.items():
        if len(values) == 1:
            result[code] = values[0]
    return result
