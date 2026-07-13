from pathlib import Path
import os
import sys
import tempfile
import unittest
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import hk_ipo
import app as backend_app


class FakeResponse:
    status_code = 200
    content = b'%PDF-1.4 test document'


def cached_item(url='https://example.test/offer.pdf'):
    return {
        'code': '01234',
        'name': 'Example IPO',
        'status': 'account_review',
        'offer_document_url': url,
        'result_document_url': None,
        'document_parse_status': 'not_requested',
    }


class HkIpoDocumentCacheTest(unittest.TestCase):
    def test_market_overview_does_not_request_ipo_data(self):
        requested_types = []

        def fetch(data_type, method_name, **kwargs):
            requested_types.append(data_type)
            return {}, 'test', False

        with patch.object(backend_app, 'fetch_with_cache', side_effect=fetch):
            response = backend_app.app.test_client().get('/api/v1/market/overview')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('hk_ipo_summary', requested_types)

    def test_sync_downloads_each_document_url_only_once(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.dict(os.environ, {'HK_IPO_CACHE_DIR': cache_dir}):
                with patch.object(hk_ipo, '_fetch_disclosures', return_value=[]):
                    with patch.object(hk_ipo, '_merge_disclosures', return_value=[cached_item()]):
                        with patch.object(hk_ipo, 'hkex_get', return_value=FakeResponse()) as download:
                            with patch.object(hk_ipo, '_parse_document_fields', return_value=({'price_low_hkd': 10}, 'parsed')):
                                hk_ipo.refresh_hk_ipo_cache(force=True)
                                hk_ipo.refresh_hk_ipo_cache(force=True)

        self.assertEqual(download.call_count, 1)

    def test_detail_uses_persisted_document_fields_without_network_access(self):
        with tempfile.TemporaryDirectory() as cache_dir:
            with patch.dict(os.environ, {'HK_IPO_CACHE_DIR': cache_dir}):
                manifest = {
                    'version': 1,
                    'items': [cached_item()],
                    'documents': {
                        'https://example.test/offer.pdf': {
                            'file_name': 'offer.pdf',
                            'parse_status': 'parsed',
                            'fields': {'price_low_hkd': 10.5, 'board_lot_shares': 100},
                        }
                    },
                }
                hk_ipo._save_manifest(manifest)

                with patch.object(hk_ipo, 'hkex_get') as download:
                    detail = hk_ipo.get_hk_ipo_detail('1234')

        self.assertEqual(detail['price_low_hkd'], 10.5)
        self.assertEqual(detail['board_lot_shares'], 100)
        download.assert_not_called()
