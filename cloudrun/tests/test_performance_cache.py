# -*- coding: utf-8 -*-
"""常规读取必须快速返回上次成功快照。"""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app


class PerformanceCacheTest(unittest.TestCase):
    def test_regular_read_returns_snapshot_without_waiting_for_source(self):
        cached = Mock()
        cached.get.return_value = None
        cached.get_stale.return_value = {'items': ['last-success']}
        with patch.object(backend_app, 'cache', cached), \
                patch.object(backend_app.factory, 'get_with_fallback') as upstream, \
                patch('services.cache._maybe_trigger_background_refresh') as refresh:
            data, source, is_cached = backend_app.fetch_with_cache(
                'convertible_list', 'get_convertible_list')

        self.assertEqual(data, {'items': ['last-success']})
        self.assertEqual(source, 'local_snapshot')
        self.assertTrue(is_cached)
        upstream.assert_not_called()
        refresh.assert_called_once()

    def test_cold_regular_read_starts_refresh_without_sync_upstream(self):
        cached = Mock()
        cached.get.return_value = None
        cached.get_stale.return_value = None
        with patch.object(backend_app, 'cache', cached), \
                patch.object(backend_app.factory, 'get_with_fallback') as upstream, \
                patch('services.cache._maybe_trigger_background_refresh') as refresh:
            data, source, is_cached = backend_app.fetch_with_cache(
                'convertible_list', 'get_convertible_list')

        self.assertEqual(data, {'total': 0, 'page': 1, 'page_size': 100, 'items': []})
        self.assertEqual(source, 'warming')
        self.assertFalse(is_cached)
        upstream.assert_not_called()
        refresh.assert_called_once()
