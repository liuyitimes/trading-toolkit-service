from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.convertible_bond import (
    _build_progress_full,
    _calc_cash_ratio,
    _is_pending_placement_visible,
    _load_cached_ma20,
    _timeline_needs_refresh,
)


class PendingPlacementVisibilityTest(unittest.TestCase):
    def test_jiangshan_stays_visible_through_its_registration_date(self):
        self.assertTrue(_is_pending_placement_visible('2026-07-13', datetime(2026, 7, 12, 12, 0)))
        self.assertTrue(_is_pending_placement_visible('2026-07-13', datetime(2026, 7, 13, 15, 0)))
        self.assertFalse(_is_pending_placement_visible('2026-07-13', datetime(2026, 7, 14, 9, 0)))

    def test_missing_registration_date_stays_visible(self):
        self.assertTrue(_is_pending_placement_visible('', datetime(2026, 7, 12, 12, 0)))

    def test_cash_ratio_uses_allocation_and_stock_price(self):
        self.assertEqual(_calc_cash_ratio(0.7848, 5.25), 14.95)

    def test_cash_ratio_handles_missing_input(self):
        self.assertEqual(_calc_cash_ratio(0, 5.25), 0)
        self.assertEqual(_calc_cash_ratio(1.2, 0), 0)

    def test_progress_full_uses_cached_stages_without_fetching_announcements(self):
        progress = _build_progress_full(
            {
                '同意注册': '2026-06-17',
                '董事会预案': '2026-05-07',
                '股东大会批准': '2026-05-09',
            },
            '申购中',
            '2026-07-14',
            '2026-07-13',
        )
        self.assertEqual(
            progress,
            '2026-05-07 董事会预案;2026-05-09 股东大会批准;'
            '2026-06-17 同意注册;2026-07-13 股权登记日;2026-07-14 申购中',
        )

    def test_complete_timeline_does_not_need_background_refresh(self):
        timeline = {
            'stage_dates': {
                '董事会预案': '2026-01-01',
                '股东大会批准': '2026-02-01',
                '交易所受理': '2026-03-01',
                '上市委通过': '2026-04-01',
                '同意注册': '2026-05-01',
            },
            'last_checked_at': None,
        }
        self.assertFalse(_timeline_needs_refresh(timeline, datetime(2026, 7, 12)))

    def test_ma20_cache_is_read_without_a_network_request(self):
        class Cache:
            def get(self, key):
                return {'value': 18.76} if key == 'convertible:ma20:600389' else None

        with patch('services.cache.get_cache_manager', return_value=Cache()):
            self.assertEqual(_load_cached_ma20(['600389', '000001']), {'600389': 18.76})
