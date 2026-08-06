from datetime import date
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import models  # noqa: F401  注册全部模型
from models.database import Base
from services.lof_premium_persistence import (
    compute_premium_persistence_batch,
    import_calendar_year,
    is_trading_day,
    latest_trading_day,
    latest_nav_dates,
    run_backfill,
    run_daily_capture,
    trading_days_between,
    upsert_observation,
)
from services.lof_fund import get_lof_list


def _session():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()


def _seed_calendar(db):
    return import_calendar_year(db, 2026)


def _last_trading_days(db, count):
    latest = latest_trading_day(db)
    days = trading_days_between(db, date(latest.year, 1, 1), latest)
    return days[-count:]


class TradingCalendarTest(unittest.TestCase):
    def test_official_holidays_are_not_trading_days(self):
        db = _session()
        _seed_calendar(db)
        db.commit()

        self.assertFalse(is_trading_day(db, date(2026, 1, 1)))
        self.assertFalse(is_trading_day(db, date(2026, 1, 3)))
        self.assertFalse(is_trading_day(db, date(2026, 2, 16)))
        self.assertFalse(is_trading_day(db, date(2026, 10, 1)))
        self.assertTrue(is_trading_day(db, date(2026, 1, 5)))
        self.assertTrue(is_trading_day(db, date(2026, 8, 6)))

    def test_weekends_and_unknown_dates_are_not_trading_days(self):
        db = _session()
        _seed_calendar(db)
        db.commit()

        self.assertFalse(is_trading_day(db, date(2026, 1, 4)))
        self.assertFalse(is_trading_day(db, date(2025, 12, 31)))

    def test_trading_days_between_returns_sorted_weekdays(self):
        db = _session()
        _seed_calendar(db)
        db.commit()

        days = trading_days_between(db, date(2026, 1, 1), date(2026, 1, 9))
        self.assertEqual(
            [day.isoformat() for day in days],
            ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09'],
        )


class ObservationUpsertTest(unittest.TestCase):
    def test_upsert_is_auditable_and_versioned(self):
        db = _session()
        _seed_calendar(db)
        first = upsert_observation(
            db,
            '161725',
            date(2026, 8, 6),
            1.1,
            1.0,
            '腾讯日K线',
            'https://ifzq.gtimg.cn/',
            '东方财富历史单位净值',
            'https://api.fund.eastmoney.com/f10/lsjz',
            date(2026, 8, 6),
            'backfill',
        )
        self.assertEqual(first['premium_rate'], 10.0)
        self.assertEqual(first['version'], 1)

        second = upsert_observation(
            db,
            '161725',
            date(2026, 8, 6),
            1.2,
            1.0,
            '腾讯日K线',
            'https://ifzq.gtimg.cn/',
            '东方财富历史单位净值',
            'https://api.fund.eastmoney.com/f10/lsjz',
            date(2026, 8, 6),
            'scheduled_capture',
        )
        self.assertEqual(second['version'], 2)
        db.commit()

        from models.lof_premium import LofPremiumObservation
        from sqlalchemy import select

        rows = db.execute(select(LofPremiumObservation)).scalars().all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].premium_rate, 20.0)

    def test_invalid_values_are_not_written(self):
        db = _session()
        _seed_calendar(db)
        self.assertIsNone(
            upsert_observation(
                db,
                '161725',
                date(2026, 8, 6),
                0,
                1.0,
                '腾讯日K线',
                None,
                '东方财富历史单位净值',
                None,
                date(2026, 8, 6),
                'backfill',
            )
        )


class PersistenceSemanticsTest(unittest.TestCase):
    def _seed_observations(self, db, premium_by_day, latest_day=date(2026, 8, 6)):
        for day, premium in premium_by_day.items():
            close = 1.0 + premium / 100.0
            upsert_observation(
                db,
                '161725',
                day,
                close,
                1.0,
                '腾讯日K线',
                'https://ifzq.gtimg.cn/',
                '东方财富历史单位净值',
                'https://api.fund.eastmoney.com/f10/lsjz',
                day,
                'backfill',
            )
        db.commit()

    def test_complete_zero_when_latest_premium_is_not_positive(self):
        db = _session()
        _seed_calendar(db)
        as_of = _last_trading_days(db, 1)[-1]
        self._seed_observations(db, {as_of: -1.0})
        result = compute_premium_persistence_batch(
            db, ['161725'], as_of=as_of
        )['161725']
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['consecutive_positive_sessions'], 0)
        self.assertIsNone(result['reason'])

    def test_complete_count_stops_at_non_positive_day(self):
        db = _session()
        _seed_calendar(db)
        days = _last_trading_days(db, 4)
        self._seed_observations(
            db,
            {
                days[3]: 1.0,
                days[2]: 1.0,
                days[1]: 1.0,
                days[0]: -0.5,
            },
        )
        result = compute_premium_persistence_batch(
            db, ['161725'], as_of=days[3]
        )['161725']
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['consecutive_positive_sessions'], 3)

    def test_partial_when_history_coverage_starts_at_year_begin(self):
        db = _session()
        _seed_calendar(db)
        # 2026-01-05 是当年首个交易日；只从该日起连续为正且无更早记录。
        self._seed_observations(
            db,
            {
                date(2026, 1, 5): 1.0,
                date(2026, 1, 6): 1.0,
                date(2026, 1, 7): 1.0,
            },
            latest_day=date(2026, 1, 7),
        )
        result = compute_premium_persistence_batch(
            db, ['161725'], as_of=date(2026, 1, 7)
        )['161725']
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['consecutive_positive_sessions'], 3)
        self.assertEqual(result['history_started_on'], '2026-01-05')
        self.assertIn('历史覆盖不足', result['reason'])

    def test_partial_with_gap_reason(self):
        db = _session()
        _seed_calendar(db)
        days = _last_trading_days(db, 5)
        self._seed_observations(
            db,
            {
                days[4]: 1.0,
                days[3]: 1.0,
                # days[2] 缺失形成历史缺口
                days[1]: 1.0,
            },
        )
        result = compute_premium_persistence_batch(
            db, ['161725'], as_of=days[4]
        )['161725']
        self.assertEqual(result['status'], 'partial')
        self.assertEqual(result['consecutive_positive_sessions'], 2)
        self.assertIn(days[2].isoformat(), result['reason'])

    def test_unavailable_when_no_observation_on_latest_trading_day(self):
        db = _session()
        _seed_calendar(db)
        days = _last_trading_days(db, 2)
        self._seed_observations(db, {days[0]: 1.0})
        result = compute_premium_persistence_batch(
            db, ['161725'], as_of=days[1]
        )['161725']
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(result['consecutive_positive_sessions'])
        self.assertIn('无同日可比观测', result['reason'])

    def test_unavailable_when_calendar_missing(self):
        db = _session()
        result = compute_premium_persistence_batch(db, ['161725'])['161725']
        self.assertEqual(result['status'], 'unavailable')
        self.assertIn('日历', result['reason'])


class BackfillAndCaptureTest(unittest.TestCase):
    def test_backfill_writes_same_day_paired_observations(self):
        db = _session()
        _seed_calendar(db)
        nav_rows = [
            {'date': '2026-01-05', 'nav': 1.0},
            {'date': '2026-01-06', 'nav': 1.0},
        ]
        close_rows = [
            {'date': '2026-01-05', 'close': 1.05},
            {'date': '2026-01-07', 'close': 1.1},
        ]
        with (
            patch(
                'services.lof_premium_persistence.fetch_em_nav_history',
                return_value=nav_rows,
            ),
            patch(
                'services.lof_premium_persistence.fetch_tencent_kline_daily',
                return_value=close_rows,
            ),
        ):
            result = run_backfill(
                db,
                year=2026,
                fund_codes=['161725'],
                as_of=date(2026, 1, 9),
            )

        self.assertTrue(result['acquired'])
        self.assertEqual(result['success_count'], 1)
        # 仅 2026-01-05 同日可配对；01-06 缺收盘价、01-07 缺净值。
        persistence = compute_premium_persistence_batch(
            db, ['161725'], as_of=date(2026, 1, 9)
        )['161725']
        self.assertEqual(persistence['status'], 'unavailable')
        self.assertEqual(persistence['reason'], '当前交易日 2026-01-09 无同日可比观测')

    def test_daily_capture_writes_only_when_same_day_nav_available(self):
        db = _session()
        _seed_calendar(db)
        universe = [{'f12': '161725', 'f13': '0', 'f14': '测试LOF'}]
        quote = [''] * 82
        quote[1] = '测试LOF'
        quote[2] = '161725'
        quote[3] = '1.1'
        quote[61] = 'LOF'
        quotes = {'161725': quote}
        with (
            patch('services.lof_fund._fetch_em_lof_rows', return_value=universe),
            patch('services.lof_fund._fetch_tencent_quotes', return_value=quotes),
            patch(
                'services.lof_premium_persistence.fetch_em_nav_history',
                return_value=[{'date': '2026-08-06', 'nav': 1.0}],
            ),
        ):
            result = run_daily_capture(db, as_of=date(2026, 8, 6))

        self.assertEqual(result['written'], 1)
        persistence = compute_premium_persistence_batch(
            db, ['161725'], as_of=date(2026, 8, 6)
        )['161725']
        self.assertEqual(persistence['status'], 'partial')
        self.assertEqual(persistence['consecutive_positive_sessions'], 1)
        self.assertIn('2026-08-05', persistence['reason'])

    def test_daily_capture_skips_when_nav_date_mismatches(self):
        db = _session()
        _seed_calendar(db)
        universe = [{'f12': '161725', 'f13': '0', 'f14': '测试LOF'}]
        quote = [''] * 82
        quote[1] = '测试LOF'
        quote[2] = '161725'
        quote[3] = '1.1'
        quote[61] = 'LOF'
        quotes = {'161725': quote}
        with (
            patch('services.lof_fund._fetch_em_lof_rows', return_value=universe),
            patch('services.lof_fund._fetch_tencent_quotes', return_value=quotes),
            patch(
                'services.lof_premium_persistence.fetch_em_nav_history',
                return_value=[{'date': '2026-08-04', 'nav': 1.0}],
            ),
        ):
            result = run_daily_capture(db, as_of=date(2026, 8, 6))

        self.assertEqual(result['written'], 0)
        self.assertEqual(result['pending_nav'], 1)
        persistence = compute_premium_persistence_batch(
            db, ['161725'], as_of=date(2026, 8, 6)
        )['161725']
        self.assertEqual(persistence['status'], 'unavailable')

    def test_latest_nav_dates_returns_actual_published_date(self):
        db = _session()
        _seed_calendar(db)
        upsert_observation(
            db,
            '161725',
            date(2026, 8, 5),
            1.05,
            1.0,
            '腾讯日K线',
            None,
            '东方财富历史单位净值',
            None,
            date(2026, 8, 4),
            'scheduled_capture',
        )
        db.commit()
        nav_map = latest_nav_dates(db, ['161725'], as_of=date(2026, 8, 6))
        self.assertEqual(nav_map['161725']['nav_date'], '2026-08-04')
        self.assertEqual(nav_map['161725']['unit_nav'], 1.0)


class LofListIntegrationTest(unittest.TestCase):
    def test_get_lof_list_attaches_premium_persistence_and_real_nav_date(self):
        db = _session()
        _seed_calendar(db)
        days = _last_trading_days(db, 3)
        latest_day = days[-1]
        prev_day = days[-2]
        gap_day = days[-3]
        for day in (prev_day, latest_day):
            upsert_observation(
                db,
                '161725',
                day,
                1.06,
                1.0,
                '腾讯日K线',
                'https://ifzq.gtimg.cn/',
                '东方财富历史单位净值',
                'https://api.fund.eastmoney.com/f10/lsjz',
                day,
                'backfill',
            )
        db.commit()

        universe = [{'f12': '161725', 'f13': '0', 'f14': '测试LOF'}]
        quote = [''] * 82
        quote[1] = '测试LOF'
        quote[2] = '161725'
        quote[3] = '1.0'
        quote[30] = '20260806150000'
        quote[61] = 'LOF'
        quote[81] = '1.0'
        quotes = {'161725': quote}

        class FakeSession:
            def __init__(self, inner):
                self.inner = inner

            def __enter__(self):
                return self.inner

            def __exit__(self, *args):
                return False

        with (
            patch('services.lof_fund._fetch_em_lof_rows', return_value=universe),
            patch('services.lof_fund._fetch_tencent_quotes', return_value=quotes),
            patch('services.lof_fund._load_execution_rules', return_value={}),
            patch('services.lof_detail.record_observations'),
            patch('models.database.SessionLocal', return_value=FakeSession(db)),
        ):
            rows = get_lof_list()

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['净值日期'], latest_day.isoformat())
        self.assertEqual(row['premium_persistence']['status'], 'partial')
        self.assertEqual(row['premium_persistence']['consecutive_positive_sessions'], 2)
        self.assertIn(gap_day.isoformat(), row['premium_persistence']['reason'])


if __name__ == '__main__':
    unittest.main()
