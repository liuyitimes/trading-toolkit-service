from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.announcement_parser import parse_placement_from_tables


class PlacementAnnouncementParserTest(unittest.TestCase):
    def test_only_original_shareholder_priority_allocation_total_is_accepted(self):
        tables = [[
            ['类别', '认购金额（元）'],
            ['控股股东', '800000000'],
            ['控股股东一致行动人', '100000000'],
            ['原股东优先配售合计', '1500000000'],
            ['网上社会公众投资者', '500000000'],
            ['合计', '2000000000'],
        ]]

        result = parse_placement_from_tables(tables)

        self.assertEqual(result['shareholder_amount'], 15.0)
        self.assertEqual(result['shareholder_ratio'], 75.0)

    def test_individual_shareholder_rows_do_not_create_a_shareholder_total(self):
        tables = [[
            ['类别', '认购金额（元）'],
            ['控股股东', '800000000'],
            ['实际控制人', '100000000'],
            ['网上社会公众投资者', '1100000000'],
            ['合计', '2000000000'],
        ]]

        result = parse_placement_from_tables(tables)

        self.assertIsNone(result['shareholder_amount'])
        self.assertIsNone(result['shareholder_ratio'])
