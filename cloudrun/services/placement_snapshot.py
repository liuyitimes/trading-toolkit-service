# -*- coding: utf-8 -*-
"""Snapshot-only reads and asynchronous refresh for pending placements."""

import json
import logging
import threading
from datetime import datetime, timedelta

from models.database import get_db_session
from models.placement_snapshot import (
    PlacementCandidate,
    PlacementObservation,
    PlacementRefreshJob,
    PlacementSnapshot,
    PlacementSourceEvidence,
)

logger = logging.getLogger('trading_toolkit')
_refresh_lock = threading.Lock()
_refresh_running = False
_scheduler_lock = threading.Lock()
_scheduler_running = False
_last_cleanup_date = None

ISSUER_TERM_FIELDS = {
    'registration_date', 'apply_date', 'per_share_allocation', 'issue_size',
    'conversion_price', 'shareholder_ratio', 'payment_date', 'ration_code',
}
MARKET_FIELDS = {'stock_price', 'stock_change', 'pb', 'ma20_price', 'record_price'}
SOURCE_PRIORITY = {
    'official': 400,
    'exchange': 400,
    'cninfo': 400,
    'issuer': 300,
    'eastmoney': 200,
    'em': 200,
    'market': 100,
    'direct': 100,
    'inferred': 0,
    'manual': 1000,
}


def _now():
    return datetime.now()


def _candidate_key(row):
    return '{}:{}'.format(str(row.get('stock_code') or ''), str(row.get('bond_code') or ''))


def _source_kind(row, fallback):
    source_kind = str(row.get('_placement_source') or row.get('source_kind') or fallback or 'market').lower()
    # The current direct pending collector is backed by Eastmoney's issuance list.
    return 'eastmoney' if source_kind == 'direct' else source_kind


def _source_priority(source_kind):
    return SOURCE_PRIORITY.get(source_kind, SOURCE_PRIORITY['market'])


def _issuer_terms_conflict(current, incoming):
    return any(
        field in incoming and incoming.get(field) not in (None, '', 0)
        and current.get(field) not in (None, '', 0)
        and incoming.get(field) != current.get(field)
        for field in ISSUER_TERM_FIELDS
    )


def _reconcile_row(current, incoming, source_kind):
    """Merge a new observation without allowing weak issuer evidence to win."""
    current = dict(current or {})
    incoming = dict(incoming or {})
    incoming_priority = _source_priority(source_kind)
    current_priority = int(current.get('_placement_issuer_terms_priority') or 0)
    conflict = _issuer_terms_conflict(current, incoming)
    result = 'accepted'

    for field in MARKET_FIELDS:
        if field in incoming:
            current[field] = incoming[field]
    for field, value in incoming.items():
        if field not in ISSUER_TERM_FIELDS and field not in MARKET_FIELDS and not field.startswith('_'):
            current[field] = value

    if not current_priority or incoming_priority > current_priority:
        for field in ISSUER_TERM_FIELDS:
            if field in incoming:
                current[field] = incoming[field]
        current['_placement_issuer_terms_priority'] = incoming_priority
    elif conflict and incoming_priority == current_priority:
        result = 'conflict'
    elif conflict:
        result = 'ignored_lower_priority'

    current['field_provenance'] = {
        'issuer_terms': source_kind if result == 'accepted' else current.get('field_provenance', {}).get('issuer_terms', 'unknown'),
        'market_fields': source_kind,
    }
    return current, result, incoming_priority


def _public_row(row):
    return {key: value for key, value in row.items() if not key.startswith('_placement_')}


def _refresh_interval(rows, now):
    imminent = False
    for row in rows:
        value = str(row.get('registration_date') or '')[:10]
        try:
            registration_date = datetime.strptime(value, '%Y-%m-%d').date()
        except ValueError:
            continue
        if 0 <= (registration_date - now.date()).days <= 1:
            imminent = True
            break
    if imminent:
        return timedelta(minutes=5)
    if now.weekday() < 5 and (now.hour, now.minute) >= (8, 30) and (now.hour, now.minute) < (18, 0):
        return timedelta(minutes=15)
    return timedelta(hours=2)


def _serialize_snapshot(snapshot, now):
    try:
        row = json.loads(snapshot.payload)
    except (TypeError, json.JSONDecodeError):
        row = {}
    interval = _refresh_interval([row], now)
    data_as_of = snapshot.data_as_of or snapshot.updated_at or now
    stale = snapshot.freshness_state == 'stale' or now - data_as_of > interval
    return _public_row(row), stale, data_as_of


def get_pending_snapshot_payload():
    """Return persisted data only; callers may independently request a refresh."""
    now = _now()
    with get_db_session() as db:
        snapshots = (
            db.query(PlacementSnapshot)
            .filter(PlacementSnapshot.deleted_at.is_(None))
            .order_by(PlacementSnapshot.registration_date.asc(), PlacementSnapshot.id.asc())
            .all()
        )
        rows = []
        stale = False
        latest_data_as_of = None
        stale_reason = None
        verification_state = 'unverified'
        review_required = False
        for snapshot in snapshots:
            row, row_stale, data_as_of = _serialize_snapshot(snapshot, now)
            if not row:
                continue
            rows.append(row)
            stale = stale or row_stale
            latest_data_as_of = max(latest_data_as_of, data_as_of) if latest_data_as_of else data_as_of
            stale_reason = stale_reason or snapshot.stale_reason
            if snapshot.verification_state == 'verified':
                verification_state = 'verified'
            review_required = review_required or bool(snapshot.review_required)

        latest_job = (
            db.query(PlacementRefreshJob)
            .filter(PlacementRefreshJob.scope == 'pending')
            .order_by(PlacementRefreshJob.requested_at.desc())
            .first()
        )
        if latest_job and latest_job.status in ('failed', 'retrying'):
            stale = True
            stale_reason = stale_reason or latest_job.last_error

    freshness_state = 'empty' if not rows else ('stale' if stale else 'fresh')
    return {
        'items': rows,
        'meta': {
            'data_as_of': latest_data_as_of.isoformat() if latest_data_as_of else None,
            'freshness_state': freshness_state,
            'stale_reason': stale_reason,
            'verification_state': verification_state,
            'review_required': review_required,
        },
    }


def snapshot_needs_refresh(payload):
    if payload['meta']['freshness_state'] in ('empty', 'stale'):
        return True
    rows = payload['items']
    if not rows:
        return True
    data_as_of = payload['meta']['data_as_of']
    if not data_as_of:
        return True
    try:
        age = _now() - datetime.fromisoformat(data_as_of)
    except ValueError:
        return True
    return age > _refresh_interval(rows, _now())


def _source_evidence(db, row, source_kind):
    identifier = str(row.get('announcement_id') or row.get('source_url') or '')
    if not identifier:
        return None
    evidence = db.query(PlacementSourceEvidence).filter_by(
        source_kind=source_kind, source_identifier=identifier
    ).first()
    if not evidence:
        evidence = PlacementSourceEvidence(
            source_kind=source_kind,
            source_identifier=identifier,
            source_url=row.get('source_url'),
        )
        db.add(evidence)
        db.flush()
    return evidence


def _persist_rows(rows, source):
    now = _now()
    with get_db_session() as db:
        for row in rows:
            key = _candidate_key(row)
            if key == ':':
                continue
            source_kind = _source_kind(row, source)
            candidate = db.query(PlacementCandidate).filter_by(candidate_key=key).first()
            if not candidate:
                candidate = PlacementCandidate(
                    candidate_key=key,
                    stock_code=str(row.get('stock_code') or ''),
                    bond_code=str(row.get('bond_code') or ''),
                )
                db.add(candidate)
                db.flush()
            snapshot = db.query(PlacementSnapshot).filter_by(candidate_id=candidate.id).first()
            if not snapshot:
                snapshot = PlacementSnapshot(candidate_id=candidate.id)
                db.add(snapshot)
                db.flush()
            try:
                current = json.loads(snapshot.payload)
            except (TypeError, json.JSONDecodeError):
                current = {}
            merged, reconciliation_result, source_priority = _reconcile_row(current, row, source_kind)
            snapshot.payload = json.dumps(merged, ensure_ascii=False, default=str)
            snapshot.registration_date = str(merged.get('registration_date') or '')[:20] or None
            snapshot.data_as_of = now
            snapshot.freshness_state = 'fresh'
            snapshot.stale_reason = None
            snapshot.deleted_at = None
            snapshot.review_required = snapshot.review_required or reconciliation_result == 'conflict'
            if source_priority >= SOURCE_PRIORITY['official']:
                snapshot.verification_state = 'verified'
            evidence = _source_evidence(db, row, source_kind)
            db.add(PlacementObservation(
                candidate_id=candidate.id,
                field_group='issuer_terms' if any(field in row for field in ISSUER_TERM_FIELDS) else 'market_fields',
                source_kind=source_kind,
                source_priority=source_priority,
                source_evidence_id=evidence.id if evidence else None,
                payload=json.dumps(row, ensure_ascii=False, default=str),
                reconciliation_result=reconciliation_result,
                input_snapshot_id=snapshot.id,
            ))


def apply_manual_issuer_terms(candidate_key, fields, actor, reason):
    """Apply an auditable, highest-priority issuer-term correction."""
    if not actor or not reason:
        raise ValueError('manual placement overrides require actor and reason')
    allowed = {key: value for key, value in dict(fields or {}).items() if key in ISSUER_TERM_FIELDS}
    if not allowed:
        raise ValueError('manual placement override requires issuer-term fields')
    with get_db_session() as db:
        candidate = db.query(PlacementCandidate).filter_by(candidate_key=candidate_key).first()
        if not candidate:
            raise ValueError('placement candidate not found')
        snapshot = db.query(PlacementSnapshot).filter_by(candidate_id=candidate.id).first()
        if not snapshot:
            raise ValueError('placement snapshot not found')
        current = json.loads(snapshot.payload)
        merged, _, priority = _reconcile_row(current, allowed, 'manual')
        snapshot.payload = json.dumps(merged, ensure_ascii=False)
        snapshot.registration_date = str(merged.get('registration_date') or '')[:20] or None
        snapshot.verification_state = 'manual_override'
        db.add(PlacementObservation(
            candidate_id=candidate.id,
            field_group='issuer_terms',
            source_kind='manual',
            source_priority=priority,
            payload=json.dumps(allowed, ensure_ascii=False),
            reconciliation_result='accepted',
            input_snapshot_id=snapshot.id,
            override_actor=actor,
            override_reason=reason,
        ))


def cleanup_retained_placement_data(now=None):
    """Soft-delete old current snapshots and expire audit records after three years."""
    now = now or _now()
    snapshot_cutoff = (now - timedelta(days=30)).date()
    observation_cutoff = now - timedelta(days=365 * 3)
    soft_deleted = 0
    with get_db_session() as db:
        snapshots = db.query(PlacementSnapshot).filter(PlacementSnapshot.deleted_at.is_(None)).all()
        for snapshot in snapshots:
            try:
                registration_date = datetime.strptime(str(snapshot.registration_date)[:10], '%Y-%m-%d').date()
            except (TypeError, ValueError):
                continue
            if registration_date < snapshot_cutoff:
                snapshot.deleted_at = now
                soft_deleted += 1
        expired_observations = (
            db.query(PlacementObservation)
            .filter(PlacementObservation.observed_at < observation_cutoff)
            .delete(synchronize_session=False)
        )
        expired_evidence = 0
        evidence = db.query(PlacementSourceEvidence).filter(
            PlacementSourceEvidence.created_at < observation_cutoff
        ).all()
        for item in evidence:
            still_referenced = db.query(PlacementObservation).filter_by(source_evidence_id=item.id).first()
            if not still_referenced:
                db.delete(item)
                expired_evidence += 1
    return {
        'soft_deleted_snapshots': soft_deleted,
        'expired_observations': expired_observations,
        'expired_evidence': expired_evidence,
    }


def _record_job(status, job_id, error=None):
    with get_db_session() as db:
        job = db.query(PlacementRefreshJob).filter_by(id=job_id).first()
        if not job:
            return
        job.status = status
        if status == 'running':
            job.started_at = _now()
            job.attempts += 1
        if status in ('succeeded', 'failed'):
            job.completed_at = _now()
        if error:
            job.last_error = str(error)[:1000]
            retry_minutes = min(60, 2 ** min(max(job.attempts, 1), 5))
            job.next_retry_at = _now() + timedelta(minutes=retry_minutes)
            return retry_minutes * 60
    return None


def _refresh(fetcher, job_id):
    global _refresh_running
    try:
        _record_job('running', job_id)
        result = fetcher()
        if isinstance(result, tuple):
            rows, source = result
        else:
            rows, source = result, 'market'
        if not isinstance(rows, list):
            raise RuntimeError('pending placement source returned an invalid payload')
        _persist_rows(rows, source)
        _record_job('succeeded', job_id)
    except Exception as exc:
        logger.warning('pending placement snapshot refresh failed: %s', exc)
        retry_seconds = _record_job('retrying', job_id, exc) or 120
        retry = threading.Timer(retry_seconds, _refresh, args=(fetcher, job_id))
        retry.daemon = True
        retry.start()
    finally:
        with _refresh_lock:
            _refresh_running = False


def schedule_pending_snapshot_refresh(fetcher):
    """Schedule at most one in-process refresh; never execute provider I/O in a request."""
    global _refresh_running
    with _refresh_lock:
        if _refresh_running:
            return None
        with get_db_session() as db:
            active = (
                db.query(PlacementRefreshJob)
                .filter(PlacementRefreshJob.scope == 'pending', PlacementRefreshJob.status.in_(['queued', 'running', 'retrying']))
                .first()
            )
            if active:
                return active.id
            job = PlacementRefreshJob(scope='pending', status='queued')
            db.add(job)
            db.flush()
            job_id = job.id
        _refresh_running = True
        threading.Thread(target=_refresh, args=(fetcher, job_id), daemon=True, name='placement-snapshot-refresh').start()
        return job_id


def _schedule_next_tick(fetcher, delay_seconds):
    timer = threading.Timer(delay_seconds, _scheduler_tick, args=(fetcher,))
    timer.daemon = True
    timer.start()


def _scheduler_tick(fetcher):
    global _last_cleanup_date
    now = _now()
    if _last_cleanup_date != now.date():
        cleanup_retained_placement_data(now)
        _last_cleanup_date = now.date()
    payload = get_pending_snapshot_payload()
    schedule_pending_snapshot_refresh(fetcher)
    interval = _refresh_interval(payload['items'], now)
    _schedule_next_tick(fetcher, interval.total_seconds())


def start_pending_snapshot_scheduler(fetcher):
    """Start one process-local cadence independent of incoming HTTP traffic."""
    global _scheduler_running
    with _scheduler_lock:
        if _scheduler_running:
            return
        _scheduler_running = True
    _scheduler_tick(fetcher)
