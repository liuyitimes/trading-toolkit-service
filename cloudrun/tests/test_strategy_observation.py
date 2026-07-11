from datetime import date, datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.closed_end import _nav_is_current
from services.hk_ipo import _classify_status


class IpoStatusTest(unittest.TestCase):
    def test_only_the_application_day_is_open(self):
        today = date(2026, 7, 12)
        self.assertEqual(_classify_status('2026-07-12', '', today), 'open')
        self.assertEqual(_classify_status('2026-07-13', '', today), 'upcoming')
        self.assertEqual(_classify_status('2026-07-11', '2026-07-20', today), 'pending')
        self.assertEqual(_classify_status('2026-07-11', '2026-07-10', today), 'listed')


class ClosedEndNavTest(unittest.TestCase):
    def test_only_recent_nav_can_produce_an_observed_discount(self):
        now = datetime(2026, 7, 12, 10, 0)
        self.assertTrue(_nav_is_current('2026-07-05', now))
        self.assertFalse(_nav_is_current('2026-07-04', now))
        self.assertFalse(_nav_is_current('', now))
