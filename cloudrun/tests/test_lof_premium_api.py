# -*- coding: utf-8 -*-
"""LOF 列表连续正溢价 HTTP 契约测试。"""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as backend_app


class LofPremiumApiTest(unittest.TestCase):
    def test_lof_list_returns_structured_premium_persistence(self):
        item = {
            'code': '161725',
            'name': '测试 LOF',
            'premium_persistence': {
                'consecutive_positive_sessions': 0,
                'status': 'complete',
                'as_of': '2026-08-03',
                'history_started_on': '2026-08-03',
                'reason': None,
            },
        }
        with patch.object(backend_app, 'fetch_with_cache', return_value=([item], 'test', False)):
            response = backend_app.app.test_client().get('/api/v1/lof/list?refresh=true')

        self.assertEqual(response.status_code, 200)
        persistence = response.get_json()['data'][0]['premium_persistence']
        self.assertEqual(persistence, item['premium_persistence'])
        self.assertEqual(persistence['consecutive_positive_sessions'], 0)
