from datetime import datetime, timedelta
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import placement_snapshot


class PlacementSnapshotPolicyTest(unittest.TestCase):
    def test_imminent_candidate_refreshes_every_five_minutes(self):
        now = datetime(2026, 7, 22, 10, 0)
        rows = [{'registration_date': '2026-07-23'}]
        self.assertEqual(placement_snapshot._refresh_interval(rows, now), timedelta(minutes=5))

    def test_regular_trading_day_refreshes_every_fifteen_minutes(self):
        now = datetime(2026, 7, 22, 10, 0)
        rows = [{'registration_date': '2026-08-10'}]
        self.assertEqual(placement_snapshot._refresh_interval(rows, now), timedelta(minutes=15))

    def test_snapshot_read_does_not_call_provider(self):
        with patch.object(placement_snapshot, 'get_db_session') as get_session:
            session = get_session.return_value.__enter__.return_value
            query = session.query.return_value
            query.filter.return_value.order_by.return_value.all.return_value = []
            query.filter.return_value.order_by.return_value.first.return_value = None
            payload = placement_snapshot.get_pending_snapshot_payload()
        self.assertEqual(payload['items'], [])
        self.assertEqual(payload['meta']['freshness_state'], 'empty')

    def test_lower_priority_terms_cannot_replace_verified_terms(self):
        current = {
            'registration_date': '2026-07-23',
            'per_share_allocation': 2.1,
            '_placement_issuer_terms_priority': placement_snapshot.SOURCE_PRIORITY['official'],
        }
        incoming = {'registration_date': '2026-07-24', 'per_share_allocation': 1.8}
        merged, result, _ = placement_snapshot._reconcile_row(current, incoming, 'eastmoney')
        self.assertEqual(result, 'ignored_lower_priority')
        self.assertEqual(merged['registration_date'], '2026-07-23')
        self.assertEqual(merged['per_share_allocation'], 2.1)

    def test_equal_priority_term_conflict_requires_review(self):
        current = {
            'registration_date': '2026-07-23',
            '_placement_issuer_terms_priority': placement_snapshot.SOURCE_PRIORITY['cninfo'],
        }
        merged, result, _ = placement_snapshot._reconcile_row(
            current, {'registration_date': '2026-07-24'}, 'official'
        )
        self.assertEqual(result, 'conflict')
        self.assertEqual(merged['registration_date'], '2026-07-23')

    def test_higher_priority_terms_replace_market_observation(self):
        current = {
            'registration_date': '2026-07-23',
            '_placement_issuer_terms_priority': placement_snapshot.SOURCE_PRIORITY['eastmoney'],
        }
        merged, result, priority = placement_snapshot._reconcile_row(
            current, {'registration_date': '2026-07-24'}, 'cninfo'
        )
        self.assertEqual(result, 'accepted')
        self.assertEqual(priority, placement_snapshot.SOURCE_PRIORITY['cninfo'])
        self.assertEqual(merged['registration_date'], '2026-07-24')

    def test_public_row_hides_internal_reconciliation_state(self):
        row = placement_snapshot._public_row({'stock_code': '001202', '_placement_issuer_terms_priority': 400})
        self.assertEqual(row, {'stock_code': '001202'})

    def test_direct_pending_collector_is_recorded_as_eastmoney(self):
        self.assertEqual(placement_snapshot._source_kind({}, 'direct'), 'eastmoney')

    def test_scheduler_uses_imminent_refresh_interval(self):
        placement_snapshot._scheduler_running = False
        with patch.object(placement_snapshot, 'cleanup_retained_placement_data'), \
             patch.object(placement_snapshot, 'get_pending_snapshot_payload', return_value={
                 'items': [{'registration_date': '2026-07-23'}], 'meta': {'freshness_state': 'fresh'}
             }), \
             patch.object(placement_snapshot, 'schedule_pending_snapshot_refresh') as schedule, \
             patch.object(placement_snapshot, '_schedule_next_tick') as schedule_next, \
             patch.object(placement_snapshot, '_now', return_value=datetime(2026, 7, 22, 10, 0)):
            placement_snapshot.start_pending_snapshot_scheduler(lambda: [])
        schedule.assert_called_once()
        self.assertEqual(schedule_next.call_args.args[1], 300)
