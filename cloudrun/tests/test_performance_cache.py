# -*- coding: utf-8 -*-
"""常规读取必须快速返回上次成功快照，不回源阻塞。

契约对齐说明（2026-10-22）：实现侧快照读取方法为 `CacheManager.get_snapshot`，
返回的 source 标记为 `snapshot`，冷启动占位由路由显式传入的 `cold_value` 提供。
本地用例原先 mock 的 `get_stale` 与 `local_snapshot` 标记属于已废弃设计，
在合并中被远程版本取代；此处按现行契约重写断言，覆盖范围不变。
"""

from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app

# 与 app.convertible_list 路由保持一致：冷启动先返回空壳，避免首屏等待上游。
COLD_LIST_VALUE = {'total': 0, 'page': 1, 'page_size': 100, 'items': []}


class PerformanceCacheTest(unittest.TestCase):
    def test_regular_read_returns_snapshot_without_waiting_for_source(self):
        cached = Mock()
        cached.get.return_value = None
        cached.get_snapshot.return_value = {'items': ['last-success']}
        with patch.object(backend_app, 'cache', cached), \
                patch.object(backend_app.factory, 'get_with_fallback') as upstream, \
                patch.object(backend_app, '_schedule_cache_refresh') as refresh:
            data, source, is_cached = backend_app.fetch_with_cache(
                'convertible_list', 'get_convertible_list')

        self.assertEqual(data, {'items': ['last-success']})
        self.assertEqual(source, 'snapshot')
        self.assertTrue(is_cached)
        # 命中快照后必须回填内存缓存，否则每次读取都要重复读盘。
        cached.set.assert_called_once()
        upstream.assert_not_called()
        refresh.assert_called_once()

    def test_cold_regular_read_starts_refresh_without_sync_upstream(self):
        cached = Mock()
        cached.get.return_value = None
        cached.get_snapshot.return_value = None
        with patch.object(backend_app, 'cache', cached), \
                patch.object(backend_app.factory, 'get_with_fallback') as upstream, \
                patch.object(backend_app, '_schedule_cache_refresh') as refresh:
            data, source, is_cached = backend_app.fetch_with_cache(
                'convertible_list', 'get_convertible_list', cold_value=COLD_LIST_VALUE)

        self.assertEqual(data, COLD_LIST_VALUE)
        self.assertEqual(source, 'warming')
        # is_cached 语义是「未回源」，冷启动占位同样不等待上游，因此为 True。
        self.assertTrue(is_cached)
        upstream.assert_not_called()
        refresh.assert_called_once()
