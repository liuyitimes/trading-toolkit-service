from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.lof_premium_persistence import fetch_em_nav_history


class _Response:
    status_code = 200

    def __init__(self, page, total_count):
        self._page = page
        self._total_count = total_count

    def json(self):
        return {
            'Data': {'LSJZList': self._page},
            'TotalCount': self._total_count,
        }


class LofHistoryPaginationTest(unittest.TestCase):
    def test_reads_all_pages_when_provider_caps_page_size_at_twenty(self):
        entries = [
            {'FSRQ': f'2026-01-{day:02d}', 'DWJZ': '1.0'}
            for day in range(1, 46)
        ]
        responses = [
            _Response(entries[:20], 45),
            _Response(entries[20:40], 45),
            _Response(entries[40:], 45),
        ]

        with patch(
            'services.lof_premium_persistence.em_get', side_effect=responses
        ) as em_get:
            rows = fetch_em_nav_history(
                '501085', date(2026, 1, 1), date(2026, 2, 28)
            )

        self.assertEqual(len(rows), 45)
        self.assertEqual(
            [call.kwargs['params']['pageIndex'] for call in em_get.call_args_list],
            [1, 2, 3],
        )


if __name__ == '__main__':
    unittest.main()
