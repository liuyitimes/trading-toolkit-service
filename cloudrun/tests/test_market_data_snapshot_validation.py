# -*- coding: utf-8 -*-
"""可转债列表与持久化快照的数据完整性回归测试。"""

from pathlib import Path
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.cache import CacheManager
from services.convertible_bond import get_convertible_bond_list


class ConvertibleListValidationTest(unittest.TestCase):
    def test_list_excludes_quote_without_required_conversion_fields(self):
        merged = pd.DataFrame([
            {
                'bond_code': '110001', 'bond_name': '完整转债', 'price': 120,
                'change_pct': 0, 'stock_code': '600001', 'stock_name': '完整正股',
                'exchange': 'SH', 'conversion_value': 100, 'premium_rate': 20,
                'double_low': 140, 'rating': 'AA', 'stock_price': 10,
                'conversion_price': 10, 'force_trigger_price': 13,
                'revise_trigger_price': 8.5, 'issue_size': 10, 'volume': 1,
                'amount': 1, 'pure_bond_value': 90, 'ytm': 2,
                'bond_floor_discount_rate': 10, 'bond_cashflows': '[]',
                'maturity_date': '2030-01-01',
            },
            {
                'bond_code': '110072', 'bond_name': '缺失转债', 'price': 44.267,
                'change_pct': 0, 'stock_code': '', 'stock_name': '',
                'exchange': 'SH', 'conversion_value': 0, 'premium_rate': 0,
                'double_low': 0, 'rating': '', 'stock_price': 0,
                'conversion_price': 0, 'force_trigger_price': 0,
                'revise_trigger_price': 0, 'issue_size': 0, 'volume': 1,
                'amount': 1, 'pure_bond_value': 0, 'ytm': 0,
                'bond_floor_discount_rate': 0, 'bond_cashflows': '[]',
                'maturity_date': '',
            },
            {
                'bond_code': '110073', 'bond_name': 'NaN 正股', 'price': 120,
                'change_pct': 0, 'stock_code': float('nan'), 'stock_name': '缺失正股',
                'exchange': 'SH', 'conversion_value': 100, 'premium_rate': 20,
                'double_low': 140, 'rating': 'AA', 'stock_price': 10,
                'conversion_price': 10, 'force_trigger_price': 13,
                'revise_trigger_price': 8.5, 'issue_size': 10, 'volume': 1,
                'amount': 1, 'pure_bond_value': 90, 'ytm': 2,
                'bond_floor_discount_rate': 10, 'bond_cashflows': '[]',
                'maturity_date': '2030-01-01',
            },
            {
                'bond_code': '110074', 'bond_name': '无穷转债', 'price': 120,
                'change_pct': 0, 'stock_code': '600074', 'stock_name': '无穷正股',
                'exchange': 'SH', 'conversion_value': float('inf'), 'premium_rate': 20,
                'double_low': 140, 'rating': 'AA', 'stock_price': 10,
                'conversion_price': 10, 'force_trigger_price': 13,
                'revise_trigger_price': 8.5, 'issue_size': 10, 'volume': 1,
                'amount': 1, 'pure_bond_value': 90, 'ytm': 2,
                'bond_floor_discount_rate': 10, 'bond_cashflows': '[]',
                'maturity_date': '2030-01-01',
            },
        ])

        with patch('services.convertible_bond._merge_bond_data', return_value=merged):
            rows = get_convertible_bond_list()

        self.assertEqual([row['bond_code'] for row in rows], ['110001'])


class ConvertibleSnapshotValidationTest(unittest.TestCase):
    def test_incomplete_list_cannot_replace_last_complete_snapshot(self):
        complete = {
            'total': 1, 'page': 1, 'page_size': 100,
            'items': [{
                'bond_code': '110001', 'bond_name': '完整转债', 'price': 120,
                'stock_code': '600001', 'stock_name': '完整正股',
                'conversion_price': 10, 'conversion_value': 100,
            }],
        }
        incomplete = {
            'total': 1, 'page': 1, 'page_size': 100,
            'items': [{
                'bond_code': '110072', 'bond_name': '缺失转债', 'price': 44.267,
                'stock_code': '', 'stock_name': '',
                'conversion_price': 0, 'conversion_value': 0,
            }],
        }

        with tempfile.TemporaryDirectory() as directory, \
                patch.dict('os.environ', {'CACHE_SNAPSHOT_DIR': directory}):
            cache = CacheManager()
            cache.set('convertible:list:data:page=1', complete, 60)
            cache.set('convertible:list:data:page=1', incomplete, 60)

            self.assertEqual(cache.get('convertible:list:data:page=1'), complete)
            self.assertEqual(cache.get_stale('convertible:list:data:page=1'), complete)

    def test_legacy_incomplete_snapshot_is_not_read_after_restart(self):
        incomplete = {
            'total': 1, 'page': 1, 'page_size': 100,
            'items': [{
                'bond_code': '110072', 'bond_name': '缺失转债', 'price': 44.267,
                'stock_code': '', 'stock_name': '',
                'conversion_price': 0, 'conversion_value': 0,
            }],
        }

        with tempfile.TemporaryDirectory() as directory, \
                patch.dict('os.environ', {'CACHE_SNAPSHOT_DIR': directory}):
            cache = CacheManager()
            snapshot_path = cache._snapshot_path('convertible:list:data:page=1')
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(
                json.dumps({'saved_at': 0, 'data': incomplete}), encoding='utf-8'
            )

            self.assertIsNone(cache.get_stale('convertible:list:data:page=1'))
