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
