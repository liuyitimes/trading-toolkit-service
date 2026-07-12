from datetime import date, datetime
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.closed_end import _nav_is_current
from services.hk_ipo import _classify_status, _extract_offer_fields


class IpoStatusTest(unittest.TestCase):
    def test_disclosure_state_never_implies_personal_eligibility(self):
        self.assertEqual(
            _classify_status({'offer_document_url': 'https://example.test/offer.pdf'}),
            'account_review',
        )
        self.assertEqual(
            _classify_status({'result_document_url': 'https://example.test/result.pdf'}),
            'result_published',
        )
        self.assertEqual(_classify_status({}), 'observation')

    def test_offer_parser_extracts_only_documented_public_fields(self):
        fields = _extract_offer_fields(
            'MaximumOfferPrice:HK$32.30 per Share. The Offer Price is currently '
            'expected to be not less than HK$30.00. Your application must be for '
            'a minimum of 100 Hong Kong Offer Shares.'
        )
        self.assertEqual(fields['price_low_hkd'], 30.0)
        self.assertEqual(fields['price_high_hkd'], 32.3)
        self.assertEqual(fields['board_lot_shares'], 100)


class ClosedEndNavTest(unittest.TestCase):
    def test_only_recent_nav_can_produce_an_observed_discount(self):
        now = datetime(2026, 7, 12, 10, 0)
        self.assertTrue(_nav_is_current('2026-07-05', now))
        self.assertFalse(_nav_is_current('2026-07-04', now))
        self.assertFalse(_nav_is_current('', now))
