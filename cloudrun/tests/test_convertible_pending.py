from datetime import datetime
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.convertible_bond import (
    _build_progress_full,
    _calc_cash_ratio,
    _fetch_kline_series,
    _fetch_em_pending_bonds,
    _get_placement_observation_state,
    _is_late_stage_observation,
    _is_pending_placement_visible,
    _load_cached_ma20,
    _timeline_needs_refresh,
    get_convertible_new_listed,
)


class PendingPlacementVisibilityTest(unittest.TestCase):
    def test_registration_date_state_keeps_expired_items_visible(self):
        now = datetime(2026, 7, 14, 9, 0)
        self.assertEqual(_get_placement_observation_state('2026-07-13', now), 'expired')
        self.assertEqual(_get_placement_observation_state('2026-07-14', now), 'eligible')
        self.assertEqual(_get_placement_observation_state('', now), 'registration_unknown')
        self.assertTrue(_is_pending_placement_visible('2026-07-13', now))

    def test_missing_registration_date_stays_visible(self):
        self.assertTrue(_is_pending_placement_visible('', datetime(2026, 7, 12, 12, 0)))

    def test_only_late_stage_or_follow_up_records_enter_observation(self):
        self.assertTrue(_is_late_stage_observation(
            {'SECURITY_START_DATE': '2026-07-13'}, {}
        ))
        self.assertTrue(_is_late_stage_observation(
            {}, {'stage_dates': {'同意注册': '2026-06-17'}}
        ))
        self.assertFalse(_is_late_stage_observation(
            {}, {'stage_dates': {'股东大会批准': '2026-05-09'}}
        ))

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

    def test_kline_uses_tencent_before_eastmoney_fallback(self):
        with (
            patch(
                'services.convertible_bond._fetch_tencent_kline_series',
                return_value=[{'date': '2026-08-05', 'close': 157.3}],
            ) as tencent_fetch,
            patch('services.convertible_bond._fetch_em_kline_series') as em_fetch,
        ):
            self.assertEqual(
                _fetch_kline_series('110102'),
                [{'date': '2026-08-05', 'close': 157.3}],
            )
            tencent_fetch.assert_called_once_with('110102', limit=500)
            em_fetch.assert_not_called()

    def test_pending_fields_use_registration_day_historical_closes(self):
        class Response:
            status_code = 200

            def json(self):
                return {
                    'result': {
                        'data': [
                            {
                                'SECURITY_CODE': '123456',
                                'CORRECODE_NAME_ABBR': '测试转债',
                                'CONVERT_STOCK_CODE': '300001',
                                'SECURITY_SHORT_NAME': '测试股份',
                                'LISTING_DATE': '',
                                'SECURITY_START_DATE': '2026-07-13',
                                'PUBLIC_START_DATE': '2026-07-14',
                                'ACTUAL_ISSUE_SCALE': 5,
                                'INITIAL_TRANSFER_PRICE': 10,
                                'FIRST_PER_PREPLACING': 0.5,
                                'RATING': 'AA',
                                'CORRECODE': '370001',
                                'ONLINE_GENERAL_LWR': 0.001,
                            }
                        ]
                    }
                }

        with (
            patch('services.convertible_bond.em_get', return_value=Response()),
            patch(
                'services.convertible_bond._load_timeline_cache',
                return_value={'300001': {'stage_dates': {'同意注册': '2026-06-01'}}},
            ),
            patch(
                'services.convertible_bond._fetch_sina_stock_quotes',
                return_value={'300001': {'price': 10.5, 'change_pct': 1.2}},
            ),
            patch(
                'services.convertible_bond._fetch_stock_fundamentals',
                return_value={'300001': {'pb': 1.8, 'total_shares': 100000000}},
            ),
            patch('services.convertible_bond._load_cached_ma20', return_value={'300001': 10}),
            patch(
                'services.convertible_bond._read_cached_kline_series',
                return_value=[
                    {'date': '2026-07-10', 'close': 9.8},
                    {'date': '2026-07-13', 'close': 10.0},
                    {'date': '2026-07-14', 'close': 9.7},
                ],
            ),
            patch('services.convertible_bond._schedule_kline_refresh_many'),
        ):
            rows = _fetch_em_pending_bonds()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['registration_close_price'], 10.0)
        self.assertEqual(rows[0]['post_registration_close_price'], 9.7)
        self.assertEqual(rows[0]['record_price'], 10.0)
        self.assertEqual(rows[0]['expected_profit'], None)
        self.assertEqual(rows[0]['safety_pad'], None)

    def test_new_listed_uses_current_year_and_progressive_three_day_gain(self):
        class FixedDatetime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 8, 6, 10, 0, tzinfo=tz)

        bonds = pd.DataFrame(
            [
                {
                    'bond_code': '123456',
                    'bond_name': '测试转债',
                    'stock_code': '300001',
                    'stock_name': '测试股份',
                    'exchange': '深',
                    'list_date': '2026-08-03',
                    'price': 128,
                    'change_pct': 1.1,
                    'premium_rate': 20,
                },
                {
                    'bond_code': '113999',
                    'bond_name': '去年转债',
                    'stock_code': '600001',
                    'stock_name': '去年股份',
                    'exchange': '沪',
                    'list_date': '2025-12-30',
                    'price': 118,
                },
            ]
        )

        def fake_kline(code, limit=500):
            if code == '123456':
                return [
                    {'date': '2026-08-03', 'close': 121},
                    {'date': '2026-08-04', 'close': 125},
                ]
            return [{'date': '2025-12-30', 'close': 118}]

        with (
            patch('services.convertible_bond.datetime', FixedDatetime),
            patch('services.convertible_bond._merge_bond_data', return_value=bonds),
            patch('services.convertible_bond._read_cached_kline_series', side_effect=fake_kline),
            patch('services.convertible_bond._schedule_kline_refresh_many'),
        ):
            rows = get_convertible_new_listed()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['bond_code'], '123456')
        self.assertEqual(rows[0]['listing_close'], 121)
        self.assertEqual(rows[0]['latest_close'], 125)
        self.assertEqual(rows[0]['three_day_stage'], 2)
        self.assertEqual(rows[0]['three_day_price'], 125)
        self.assertEqual(rows[0]['three_day_gain'], 25.0)
        self.assertEqual(rows[0]['gain_since_listing'], 3.31)
