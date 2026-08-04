# -*- coding: utf-8 -*-
"""LOF 溢价持续性的公开服务边界测试。"""

from datetime import date
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.lof_premium_persistence import calculate_premium_persistence


class PremiumPersistenceTest(unittest.TestCase):
    def test_positive_sessions_cross_a_weekend_without_interruption(self):
        result = calculate_premium_persistence(
            fund_code='161725',
            trading_days=[date(2026, 7, 30), date(2026, 7, 31), date(2026, 8, 3)],
            observations={
                date(2026, 7, 30): 1.2,
                date(2026, 7, 31): 0.3,
                date(2026, 8, 3): 2.1,
            },
            as_of=date(2026, 8, 3),
            coverage_started_on=date(2026, 7, 1),
        )

        self.assertEqual(result['consecutive_positive_sessions'], 3)
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['as_of'], '2026-08-03')
        self.assertIsNone(result['reason'])

    def test_current_non_positive_observation_is_a_real_complete_zero(self):
        result = calculate_premium_persistence(
            fund_code='161725',
            trading_days=[date(2026, 8, 3)],
            observations={date(2026, 8, 3): 0},
            as_of=date(2026, 8, 3),
            coverage_started_on=date(2026, 1, 1),
        )

        self.assertEqual(result['consecutive_positive_sessions'], 0)
        self.assertEqual(result['status'], 'complete')
        self.assertIsNone(result['reason'])

    def test_missing_trading_day_returns_partial_lower_bound(self):
        result = calculate_premium_persistence(
            fund_code='161725',
            trading_days=[date(2026, 7, 30), date(2026, 7, 31), date(2026, 8, 3)],
            observations={
                date(2026, 7, 30): 1.2,
                date(2026, 8, 3): 2.1,
            },
            as_of=date(2026, 8, 3),
            coverage_started_on=date(2026, 7, 1),
        )

        self.assertEqual(result['consecutive_positive_sessions'], 1)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('2026-07-31', result['reason'])

    def test_current_observation_missing_is_unavailable(self):
        result = calculate_premium_persistence(
            fund_code='161725',
            trading_days=[date(2026, 8, 3)],
            observations={},
            as_of=date(2026, 8, 3),
            coverage_started_on=date(2026, 1, 1),
        )

        self.assertIsNone(result['consecutive_positive_sessions'])
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('同日可比', result['reason'])

    def test_yearly_backfill_boundary_returns_partial(self):
        result = calculate_premium_persistence(
            fund_code='161725',
            trading_days=[date(2026, 1, 2), date(2026, 1, 5)],
            observations={date(2026, 1, 2): 1.0, date(2026, 1, 5): 1.0},
            as_of=date(2026, 1, 5),
            coverage_started_on=date(2026, 1, 2),
        )

        self.assertEqual(result['consecutive_positive_sessions'], 2)
        self.assertEqual(result['status'], 'partial')
        self.assertIn('历史覆盖起点', result['reason'])
