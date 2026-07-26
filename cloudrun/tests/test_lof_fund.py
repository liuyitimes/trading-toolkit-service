from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.lof_fund import (
    _derive_hot_direction,
    get_lof_market_summary,
    _latest_trading_weekday,
    _parse_row,
    _previous_trading_weekday,
    _resolve_execution_rule,
    _summarize_daily_subscriptions,
)
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


class LofMarketOverviewTest(unittest.TestCase):
    def test_previous_trading_weekday_skips_weekend(self):
        monday = datetime(2026, 7, 13, 10, 0, tzinfo=CST)
        self.assertEqual(_previous_trading_weekday(monday).isoformat(), '2026-07-10')

    def test_hot_direction_uses_turnover_weighted_positive_premium(self):
        now = datetime(2026, 7, 10, 15, 30, tzinfo=CST)
        items = [
            {'代码': '100001', '名称': '科技一号', '报价有效': True, '溢价率': 5.0, '成交额': 100, '行情时间': '2026-07-10T15:00:00+08:00'},
            {'代码': '100002', '名称': '科技二号', '报价有效': True, '溢价率': 3.0, '成交额': 300, '行情时间': '2026-07-10T15:00:00+08:00'},
            {'代码': '200001', '名称': '资源一号', '报价有效': True, '溢价率': 4.0, '成交额': 100, '行情时间': '2026-07-10T15:00:00+08:00'},
            {'代码': '999999', '名称': '未分类基金', '报价有效': True, '溢价率': 9.0, '成交额': 500, '行情时间': '2026-07-10T15:00:00+08:00'},
        ]
        taxonomy = {
            'funds': {
                '100001': {'theme': '科技创新', 'basis': '基金产品名称'},
                '100002': {'theme': '科技创新', 'basis': '基金产品名称'},
                '200001': {'theme': '资源周期', 'basis': '基金产品名称'},
            }
        }

        result = _derive_hot_direction(items, taxonomy, now)

        self.assertEqual(result['status'], 'available')
        self.assertIsNone(result['reason'])
        self.assertEqual(result['name'], '资源周期')
        self.assertEqual(result['sample_count'], 1)
        self.assertEqual(result['weighted_premium'], 4.0)
        self.assertEqual(result['unclassified_count'], 1)
        self.assertEqual(result['as_of'], '2026-07-10')
        self.assertEqual(result['source'], 'LOF 主题分类表（基金产品名称）')
        self.assertEqual(result['retrieved_at'], now.isoformat())
        self.assertEqual(result['constituents'], [{
            'code': '200001',
            'name': '资源一号',
            'basis': '基金产品名称',
            'premium': 4.0,
            'turnover_yuan': 100.0,
        }])

    def test_market_summary_exposes_hot_direction_evidence(self):
        items = [{
            '代码': '200001',
            '名称': '资源一号',
            '报价有效': True,
            '溢价率': 4.0,
            '成交额': 100,
            '行情时间': '2026-07-10T15:00:00+08:00',
            '交易路径已验证': False,
        }]
        taxonomy = {'funds': {
            '200001': {'theme': '资源周期', 'basis': '基金产品名称'},
        }}
        with patch('services.lof_fund.get_lof_list', return_value=items), \
                patch('services.lof_fund._load_theme_taxonomy', return_value=taxonomy):
            result = get_lof_market_summary()

        self.assertEqual(result['hot_direction']['status'], 'available')
        self.assertEqual(result['hot_direction']['constituents'][0]['code'], '200001')

    def test_hot_direction_is_unavailable_without_classified_positive_premiums(self):
        now = datetime(2026, 7, 10, 15, 30, tzinfo=CST)
        result = _derive_hot_direction([
            {
                '代码': '999999',
                '报价有效': True,
                '溢价率': 9.0,
                '成交额': 500,
                '行情时间': '2026-07-10T15:00:00+08:00',
            },
        ], {'funds': {}}, now)

        self.assertEqual(result['status'], 'unavailable')
        self.assertEqual(result['reason'], '有效正溢价分类样本不足')
        self.assertIsNone(result['name'])
        self.assertEqual(result['unclassified_count'], 1)
        self.assertEqual(result['as_of'], '2026-07-10')
        self.assertEqual(result['source'], 'LOF 主题分类表')
        self.assertEqual(result['retrieved_at'], now.isoformat())

    def test_daily_subscription_summary_separates_limit_subjects(self):
        now = datetime(2026, 7, 13, 10, 0, tzinfo=CST)
        records = [
            {
                'fund_code': '100001',
                'share_class': 'A',
                'share_date': '2026-07-10',
                'share_unit': 'shares',
                'net_share_change': 1000,
                'nav': 2.0,
                'nav_date': '2026-07-10',
                'source_url': 'https://example.test/share/100001',
                'retrieved_at': '2026-07-11T08:00:00+08:00',
                'non_subscription_adjustments_excluded': True,
                'limit_subject': 'account',
                'limit_amount': 600,
                'limit_source_url': 'https://example.test/limit/100001',
                'limit_effective_from': '2026-07-01',
                'limit_effective_to': '2026-07-31',
                'all_channels_verified': True,
            },
            {
                'fund_code': '200001',
                'share_class': 'A',
                'share_date': '2026-07-10',
                'share_unit': '10k_shares',
                'net_share_change': 1,
                'nav': 1.0,
                'nav_date': '2026-07-10',
                'source_url': 'https://example.test/share/200001',
                'retrieved_at': '2026-07-11T08:00:00+08:00',
                'non_subscription_adjustments_excluded': True,
                'limit_subject': 'investor',
                'limit_amount': 2500,
                'limit_source_url': 'https://example.test/limit/200001',
                'limit_effective_from': '2026-07-01',
                'limit_effective_to': '2026-07-31',
                'all_channels_verified': True,
            },
        ]

        result = _summarize_daily_subscriptions(records, now)

        self.assertEqual(result['status'], 'available')
        self.assertEqual(result['share_date'], '2026-07-10')
        self.assertEqual(result['capital_yuan'], 12000.0)
        self.assertEqual(result['account_count_lower_bound'], 4)
        self.assertEqual(result['investor_limit_lower_bound'], 4)

    def test_daily_subscription_summary_rejects_unverified_records(self):
        now = datetime(2026, 7, 13, 10, 0, tzinfo=CST)
        record = {
            'fund_code': '100001',
            'share_date': '2026-07-10',
            'share_unit': 'shares',
            'net_share_change': 1000,
            'nav': 1.0,
            'nav_date': '2026-07-10',
            'source_url': '',
            'retrieved_at': '2026-07-11T08:00:00+08:00',
            'non_subscription_adjustments_excluded': False,
        }

        result = _summarize_daily_subscriptions([record], now)

        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['capital_yuan'])

    def test_daily_subscription_summary_requires_boolean_evidence_flags(self):
        now = datetime(2026, 7, 13, 10, 0, tzinfo=CST)
        record = {
            'fund_code': '100001',
            'share_class': 'A',
            'share_date': '2026-07-10',
            'share_unit': 'shares',
            'net_share_change': 1000,
            'nav': 1.0,
            'nav_date': '2026-07-10',
            'source_url': 'https://example.test/share/100001',
            'retrieved_at': '2026-07-11T08:00:00+08:00',
            'non_subscription_adjustments_excluded': 'true',
        }

        result = _summarize_daily_subscriptions([record], now)

        self.assertEqual(result['status'], 'unavailable')
