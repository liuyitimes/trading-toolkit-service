from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.lof_fund import _latest_trading_weekday, _parse_row, _resolve_execution_rule
from services.normalizer import normalize_lof


CST = timezone(timedelta(hours=8))


def evidence(checked_at):
    return {
        'url': 'https://example.test/rule',
        'checked_at': checked_at.isoformat(),
        'name': 'test source',
    }


class LofExecutionRuleTest(unittest.TestCase):
    def test_current_evidence_produces_a_verified_trade_path(self):
        now = datetime(2026, 7, 12, 10, 0, tzinfo=CST)
        rule = {
            'subscription_status': 'open',
            'subscription_limit': 10000,
            'custody_transfer': True,
            'sell_available_date': '2026-07-15',
            'sources': {
                'subscription': evidence(now),
                'custody_transfer': evidence(now - timedelta(days=2)),
                'sell_available_date': evidence(now - timedelta(days=2)),
            },
        }
        with patch('services.lof_fund._load_execution_rules', return_value={'161725': rule}):
            resolved = _resolve_execution_rule('161725', now)

        self.assertTrue(resolved['subscription_open'])
        self.assertTrue(resolved['trade_path_verified'])
        self.assertEqual(resolved['subscription_limit'], 10000)

    def test_stale_subscription_rule_is_not_executable(self):
        now = datetime(2026, 7, 12, 10, 0, tzinfo=CST)
        rule = {
            'subscription_status': 'open',
            'subscription_limit': 10000,
            'custody_transfer': True,
            'sell_available_date': '2026-07-15',
            'sources': {
                'subscription': evidence(now - timedelta(days=2)),
                'custody_transfer': evidence(now),
                'sell_available_date': evidence(now),
            },
        }
        with patch('services.lof_fund._load_execution_rules', return_value={'161725': rule}):
            resolved = _resolve_execution_rule('161725', now)

        self.assertFalse(resolved['subscription_open'])
        self.assertFalse(resolved['trade_path_verified'])
        self.assertEqual(resolved['subscription_status'], '待核验')

    def test_previous_calendar_day_subscription_is_not_current(self):
        now = datetime(2026, 7, 12, 10, 0, tzinfo=CST)
        rule = {
            'subscription_status': 'open',
            'subscription_limit': 10000,
            'custody_transfer': True,
            'sell_available_date': '2026-07-15',
            'sources': {
                'subscription': evidence(now - timedelta(hours=12)),
                'custody_transfer': evidence(now),
                'sell_available_date': evidence(now),
            },
        }
        with patch('services.lof_fund._load_execution_rules', return_value={'161725': rule}):
            resolved = _resolve_execution_rule('161725', now)

        self.assertFalse(resolved['subscription_open'])

    def test_past_sell_date_is_not_a_verified_trade_path(self):
        now = datetime(2026, 7, 12, 10, 0, tzinfo=CST)
        rule = {
            'subscription_status': 'open',
            'subscription_limit': 10000,
            'custody_transfer': True,
            'sell_available_date': '2026-07-11',
            'sources': {
                'subscription': evidence(now),
                'custody_transfer': evidence(now),
                'sell_available_date': evidence(now),
            },
        }
        with patch('services.lof_fund._load_execution_rules', return_value={'161725': rule}):
            resolved = _resolve_execution_rule('161725', now)

        self.assertFalse(resolved['trade_path_verified'])
        self.assertIsNone(resolved['expected_sell_date'])

    def test_weekend_uses_the_last_trading_weekday_for_quote_freshness(self):
        now = datetime(2026, 7, 12, 10, 0, tzinfo=CST)
        self.assertEqual(_latest_trading_weekday(now).isoformat(), '2026-07-10')

    def test_quote_uses_tencent_price_and_unit_nav(self):
        now = datetime(2026, 7, 12, 10, 0, tzinfo=CST)
        row = {
            'f12': '161725',
            'f13': '0',
            'f14': '招商中证白酒',
        }
        quote = [''] * 82
        quote[1] = '招商中证白酒'
        quote[2] = '161725'
        quote[3] = '1.1'
        quote[30] = '20260710150000'
        quote[32] = '2.0'
        quote[36] = '100'
        quote[37] = '10'
        quote[61] = 'LOF'
        quote[81] = '1.0'
        parsed = _parse_row(row, quote, _resolve_execution_rule('161725', now), now)
        self.assertTrue(parsed['报价有效'])
        self.assertEqual(parsed['净值日期'], '2026-07-10')
        self.assertEqual(parsed['溢价率'], 10.0)
        self.assertEqual(parsed['成交额'], 100000)

    def test_normalizer_preserves_execution_evidence_fields(self):
        normalized = normalize_lof({
            '代码': '161725',
            '名称': '招商中证白酒',
            '交易所': '深',
            '最新价': 1.1,
            '估值': 1.0,
            '溢价率': 10.0,
            '报价有效': True,
            '可申购': True,
            '单账户限额': 10000,
            '可转托管': True,
            '预计可卖出日': '2026-07-15',
            '交易路径已验证': True,
            '近5日平均成交额': 500000,
            '规则证据': {'subscription': {'current': True}},
        })
        self.assertTrue(normalized['valid_quote'])
        self.assertEqual(normalized['subscription_limit'], 10000)
        self.assertEqual(normalized['five_day_avg_turnover'], 500000)
        self.assertTrue(normalized['trade_path_verified'])
