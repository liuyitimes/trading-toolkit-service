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
    """可恢复快照的写入与加载边界。

    契约对齐说明（2026-10-22）：快照存储为单文件（`CACHE_SNAPSHOT_PATH`），
    读取方法为 `get_snapshot`。原先基于 `CACHE_SNAPSHOT_DIR` / `get_stale` 的
    分键目录设计在合并中被远程版本取代，此处按现行存储重写，规格要求不变。
    """

    KEY = 'convertible:list:data:page=1'

    COMPLETE = {
        'total': 1, 'page': 1, 'page_size': 100,
        'items': [{
            'bond_code': '110001', 'bond_name': '完整转债', 'price': 120,
            'stock_code': '600001', 'stock_name': '完整正股',
            'conversion_price': 10, 'conversion_value': 100,
        }],
    }
    INCOMPLETE = {
        'total': 1, 'page': 1, 'page_size': 100,
        'items': [{
            'bond_code': '110072', 'bond_name': '缺失转债', 'price': 44.267,
            'stock_code': '', 'stock_name': '',
            'conversion_price': 0, 'conversion_value': 0,
        }],
    }

    def _cache_in(self, directory):
        snapshot_path = str(Path(directory) / 'api-cache.json')
        with patch.dict('os.environ', {'CACHE_SNAPSHOT_PATH': snapshot_path}):
            return CacheManager(), snapshot_path

    def test_incomplete_list_cannot_replace_last_complete_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            cache, _ = self._cache_in(directory)
            cache.set(self.KEY, self.COMPLETE, 60)
            cache.set(self.KEY, self.INCOMPLETE, 60)

            # 快照必须保留最后一个合格载荷，不合格刷新不得覆盖。
            self.assertEqual(cache.get_snapshot(self.KEY), self.COMPLETE)

    def test_empty_list_cannot_replace_last_complete_snapshot(self):
        empty = {'total': 0, 'page': 1, 'page_size': 100, 'items': []}
        with tempfile.TemporaryDirectory() as directory:
            cache, _ = self._cache_in(directory)
            cache.set(self.KEY, self.COMPLETE, 60)
            cache.set(self.KEY, empty, 60)

            # 上游故障返回空集合时，不应把用户可见的最后一版数据清空。
            self.assertEqual(cache.get_snapshot(self.KEY), self.COMPLETE)

    def test_legacy_incomplete_snapshot_is_not_read_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot_path = Path(directory) / 'api-cache.json'
            snapshot_path.write_text(
                json.dumps({self.KEY: {'updated_at': 0, 'value': self.INCOMPLETE}}),
                encoding='utf-8',
            )
            cache, _ = self._cache_in(directory)

            self.assertIsNone(cache.get_snapshot(self.KEY))
