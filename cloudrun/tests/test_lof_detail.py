from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.lof_detail import build_lof_detail, get_lof_detail, get_observations, record_observations
import app as backend_app


def current_lof(**overrides):
    item = {
        'code': '161725',
        'name': 'Example LOF',
        'exchange': 'sz',
        'price': 1.1,
        'valuation': 1.0,
        'premium': 10.0,
        'amount': 200.0,
        'volume': 100.0,
        'quote_at': '2026-07-14T15:00:00+08:00',
        'nav_date': '2026-07-14',
        'nav_source': 'verified quote',
        'valid_quote': True,
        'subscription_open': True,
        'subscription_limit': 10000,
        'custody_transfer': True,
        'expected_sell_date': '2026-07-15',
        'trade_path_verified': True,
        'verification_evidence': {'subscription': {'url': 'https://example.test/rule'}},
    }
    item.update(overrides)
    return item


class LofDetailTest(unittest.TestCase):
    def test_detail_endpoint_returns_the_normalized_detail_contract(self):
        expected = {'code': '161725', 'strategy_status': 'observation'}
        with patch.object(backend_app, 'get_lof_detail', return_value=expected):
            response = backend_app.app.test_client().get('/api/v1/lof/161725/detail')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()['data'], expected)

    def test_valid_observations_are_persisted_by_session_date(self):
        with tempfile.TemporaryDirectory() as data_dir:
            with patch.dict(os.environ, {'LOF_DETAIL_DATA_DIR': data_dir}):
                record_observations([current_lof()])
                record_observations([current_lof(price=1.12, premium=12.0)])
                history = get_observations('161725')

        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]['price'], 1.12)
        self.assertEqual(history[0]['premium'], 12.0)

    def test_detail_keeps_holdings_unavailable_without_verified_disclosure(self):
        history = [
            {'observed_at': f'2026-07-{day:02d}T15:00:00+08:00', 'price': 1 + day / 100,
             'valuation': 1, 'premium': day, 'amount': 100 + day, 'volume': 10 + day}
            for day in range(1, 6)
        ]

        detail = build_lof_detail(current_lof(), history, None)

        self.assertTrue(detail['premium']['persistence']['five_session']['available'])
        self.assertEqual(detail['instrument']['price'], 1.1)
        self.assertFalse(detail['holdings']['available'])
        self.assertEqual(detail['holdings']['status'], 'unavailable')
        self.assertEqual(detail['strategy_status'], 'executable_candidate')

    def test_detail_rejects_stale_holdings_disclosure(self):
        with tempfile.TemporaryDirectory() as data_dir:
            holdings_path = Path(data_dir) / 'holdings.json'
            holdings_path.write_text(
                '{"items":{"161725":{"as_of":"2025-01-01","source":{"url":"https://manager.test/report","kind":"manager_report","retrieved_at":"2025-01-02T10:00:00+08:00"},"top_holdings":[]}}}',
                encoding='utf-8',
            )
            with patch.dict(os.environ, {'LOF_DETAIL_DATA_DIR': data_dir}):
                with patch('services.lof_detail.get_lof_list', return_value=[]):
                    with patch('services.lof_detail.normalize_lof_list', return_value=[current_lof()]):
                        detail = get_lof_detail('161725')

        self.assertFalse(detail['holdings']['available'])
        self.assertEqual(detail['holdings']['status'], 'stale')

    def test_detail_exposes_fresh_holdings_with_verifiable_metadata(self):
        with tempfile.TemporaryDirectory() as data_dir:
            holdings_path = Path(data_dir) / 'holdings.json'
            holdings_path.write_text(
                '{"items":{"161725":{"as_of":"2026-07-14","source":{"url":"https://manager.test/report","kind":"manager_report","retrieved_at":"2026-07-14T10:00:00+08:00"},"concentration_pct":42.5,"top_holdings":[{"name":"Example Holding","weight_pct":8.2}]}}}',
                encoding='utf-8',
            )
            with patch.dict(os.environ, {'LOF_DETAIL_DATA_DIR': data_dir}):
                with patch('services.lof_detail.get_lof_list', return_value=[]):
                    with patch('services.lof_detail.normalize_lof_list', return_value=[current_lof()]):
                        detail = get_lof_detail('161725')

        self.assertTrue(detail['holdings']['available'])
        self.assertEqual(detail['holdings']['top_holdings'][0]['name'], 'Example Holding')
