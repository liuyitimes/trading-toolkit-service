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
)

logger = logging.getLogger('trading_toolkit')
_refresh_lock = threading.Lock()
_refresh_running = False


def _now():
    return datetime.now()


def _candidate_key(row):
    return '{}:{}'.format(str(row.get('stock_code') or ''), str(row.get('bond_code') or ''))


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
    return row, stale, data_as_of


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


def _persist_rows(rows, source):
    now = _now()
    with get_db_session() as db:
        active_keys = set()
        for row in rows:
            key = _candidate_key(row)
            if key == ':':
                continue
            active_keys.add(key)
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
            snapshot.payload = json.dumps(row, ensure_ascii=False, default=str)
            snapshot.registration_date = str(row.get('registration_date') or '')[:20] or None
            snapshot.data_as_of = now
            snapshot.freshness_state = 'fresh'
            snapshot.stale_reason = None
            snapshot.deleted_at = None
            db.add(PlacementObservation(
                candidate_id=candidate.id,
                field_group='snapshot',
                source_kind=source or 'market',
                source_priority=1,
                payload=snapshot.payload,
                reconciliation_result='accepted',
                input_snapshot_id=snapshot.id,
            ))
        # Do not hide a current candidate merely because an upstream response is incomplete.
        # Lifecycle cleanup is performed separately after the 30-day retention period.


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
