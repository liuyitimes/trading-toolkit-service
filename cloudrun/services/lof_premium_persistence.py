# -*- coding: utf-8 -*-
"""可审计的 LOF 同日溢价观测、回补和连续性计算。"""

from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
import logging

from sqlalchemy import text

from models.database import SessionLocal, get_db_session
from models.lof_premium import LofPremiumJob, LofPremiumObservation, TradingCalendar
from services.http_client import em_get, tencent_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

_CST = timezone(timedelta(hours=8))
_EM_FUND_NAV_URL = 'https://api.fund.eastmoney.com/f10/lsjz'
_TENCENT_KLINE_URL = 'https://web.ifzq.gtimg.cn/appstock/app/kline/kline'
_EM_NAV_SOURCE = '东方财富基金历史单位净值'
_TENCENT_KLINE_SOURCE = '腾讯财经日K线'


def _iso(value):
    return value.isoformat() if value else None


def calculate_premium_persistence(*, fund_code, trading_days, observations, as_of, coverage_started_on):
    """从一个基金的已验证日度输入计算连续正溢价，不依赖缓存事实表。"""
    ordered_days = sorted(set(day for day in trading_days if day <= as_of))
    if as_of not in ordered_days:
        return {
            'consecutive_positive_sessions': None,
            'status': 'unavailable',
            'as_of': _iso(as_of),
            'history_started_on': None,
            'reason': '当前日期未导入沪深共同交易日历',
        }
    if as_of not in observations:
        return {
            'consecutive_positive_sessions': None,
            'status': 'unavailable',
            'as_of': _iso(as_of),
            'history_started_on': None,
            'reason': '当前交易日缺少同日可比的收盘价和已公布单位净值',
        }
    if observations[as_of] <= 0:
        return {
            'consecutive_positive_sessions': 0,
            'status': 'complete',
            'as_of': _iso(as_of),
            'history_started_on': _iso(as_of),
            'reason': None,
        }

    count = 0
    first_positive = as_of
    for trading_day in reversed(ordered_days):
        if trading_day > as_of:
            continue
        premium = observations.get(trading_day)
        if premium is None:
            return {
                'consecutive_positive_sessions': count,
                'status': 'partial',
                'as_of': _iso(as_of),
                'history_started_on': _iso(first_positive),
                'reason': f'{trading_day.isoformat()} 缺少同日可比观测，历史不足',
            }
        if premium <= 0:
            return {
                'consecutive_positive_sessions': count,
                'status': 'complete',
                'as_of': _iso(as_of),
                'history_started_on': _iso(first_positive),
                'reason': None,
            }
        count += 1
        first_positive = trading_day

    if coverage_started_on and coverage_started_on in ordered_days and first_positive <= coverage_started_on:
        return {
            'consecutive_positive_sessions': count,
            'status': 'partial',
            'as_of': _iso(as_of),
            'history_started_on': _iso(first_positive),
            'reason': f'连续序列触及历史覆盖起点 {coverage_started_on.isoformat()}，历史不足',
        }
    return {
        'consecutive_positive_sessions': count,
        'status': 'complete',
        'as_of': _iso(as_of),
        'history_started_on': _iso(first_positive),
        'reason': None,
    }


def persistence_for_funds(fund_codes, as_of=None):
    """批量读取列表所需的持续性；读取路径绝不写入观测。"""
    codes = [str(code) for code in fund_codes if code]
    if not codes:
        return {}
    reference_date = as_of or datetime.now(_CST).date()
    unavailable = {
        'consecutive_positive_sessions': None,
        'status': 'unavailable',
        'as_of': None,
        'history_started_on': None,
        'reason': '尚未导入交易日历或历史观测',
    }
    try:
        with get_db_session() as db:
            days = [row[0] for row in db.query(TradingCalendar.trading_date)
                    .filter(TradingCalendar.trading_date <= reference_date)
                    .order_by(TradingCalendar.trading_date).all()]
            if not days:
                return {code: dict(unavailable) for code in codes}
            effective_as_of = days[-1]
            observations = db.query(LofPremiumObservation).filter(
                LofPremiumObservation.fund_code.in_(codes),
                LofPremiumObservation.trading_date <= effective_as_of,
            ).all()
    except Exception as exc:
        logger.warning('[LOF] premium persistence unavailable: %s', exc)
        return {code: dict(unavailable) for code in codes}

    by_code = {code: {} for code in codes}
    for observation in observations:
        by_code.setdefault(observation.fund_code, {})[observation.trading_date] = float(observation.premium_rate)
    current_year_days = [day for day in days if day.year == effective_as_of.year]
    coverage_start = current_year_days[0] if current_year_days else None
    return {
        code: calculate_premium_persistence(
            fund_code=code,
            trading_days=days,
            observations=by_code.get(code, {}),
            as_of=effective_as_of,
            coverage_started_on=coverage_start,
        )
        for code in codes
    }


def upsert_observation(*, fund_code, trading_date, close_price, unit_nav,
                       price_source, price_source_url, nav_source, nav_source_url,
                       nav_date, captured_by):
    """对同基金同交易日实施可审计修订式 upsert。"""
    if not fund_code or close_price <= 0 or unit_nav <= 0 or nav_date != trading_date:
        return False
    premium_rate = round((close_price / unit_nav - 1) * 100, 6)
    with get_db_session() as db:
        record = db.query(LofPremiumObservation).filter_by(
            fund_code=str(fund_code), trading_date=trading_date,
        ).one_or_none()
        if record is None:
            record = LofPremiumObservation(
                fund_code=str(fund_code), trading_date=trading_date,
                close_price=close_price, unit_nav=unit_nav, premium_rate=premium_rate,
                price_source=price_source, price_source_url=price_source_url,
                nav_source=nav_source, nav_source_url=nav_source_url, nav_date=nav_date,
                captured_by=captured_by,
            )
            db.add(record)
        else:
            changed = any((
                float(record.close_price) != close_price,
                float(record.unit_nav) != unit_nav,
                record.nav_date != nav_date,
                record.price_source_url != price_source_url,
                record.nav_source_url != nav_source_url,
            ))
            record.close_price = close_price
            record.unit_nav = unit_nav
            record.premium_rate = premium_rate
            record.price_source = price_source
            record.price_source_url = price_source_url
            record.nav_source = nav_source
            record.nav_source_url = nav_source_url
            record.nav_date = nav_date
            record.captured_by = captured_by
            if changed:
                record.source_version += 1
        return True


def import_trading_calendar(trading_days, *, source, source_version=None):
    """导入已核验的沪深共同交易日；调用方负责提供官方年度数据。"""
    imported = 0
    with get_db_session() as db:
        for trading_day in sorted(set(trading_days)):
            existing = db.get(TradingCalendar, trading_day)
            if existing is None:
                db.add(TradingCalendar(
                    trading_date=trading_day, source=source, source_version=source_version,
                ))
                imported += 1
            else:
                existing.source = source
                existing.source_version = source_version
    return imported


def _market_for_code(code):
    return 'sh' if str(code).startswith(('5', '6')) else 'sz'


def _parse_date(value):
    try:
        return datetime.strptime(str(value)[:10], '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def fetch_nav_history(fund_code, year):
    """读取东方财富已公布单位净值，不以行情时间伪造其日期。"""
    values = {}
    for page in range(1, 100):
        response = em_get(_EM_FUND_NAV_URL, params={
            'fundCode': fund_code, 'pageIndex': page, 'pageSize': 500,
        }, headers={'Referer': 'https://fundf10.eastmoney.com/'}, timeout=20)
        if response.status_code != 200:
            break
        data = response.json().get('Data') or {}
        rows = data.get('LSJZList') or []
        for row in rows:
            nav_date = _parse_date(row.get('FSRQ'))
            nav = safe_float(row.get('DWJZ'))
            if nav_date and nav_date.year == year and nav > 0:
                values[nav_date] = nav
        total_pages = int(data.get('TotalPages') or 1)
        if page >= total_pages:
            break
    return values


def fetch_close_history(fund_code, year):
    """读取腾讯日 K 线收盘价，保留交易日期供同日交集配对。"""
    symbol = f'{_market_for_code(fund_code)}{fund_code}'
    response = tencent_get(_TENCENT_KLINE_URL, params={
        'param': f'{symbol},day,{year}-01-01,{year}-12-31,1000',
    }, timeout=20)
    if response.status_code != 200:
        return {}
    rows = ((response.json().get('data') or {}).get(symbol) or {}).get('day') or []
    values = {}
    for row in rows:
        if len(row) < 3:
            continue
        trading_day = _parse_date(row[0])
        close_price = safe_float(row[2])
        if trading_day and trading_day.year == year and close_price > 0:
            values[trading_day] = close_price
    return values


def backfill_fund(fund_code, year):
    navs = fetch_nav_history(fund_code, year)
    closes = fetch_close_history(fund_code, year)
    with get_db_session() as db:
        calendar_days = {
            row[0] for row in db.query(TradingCalendar.trading_date)
            .filter(TradingCalendar.trading_date >= date(year, 1, 1))
            .filter(TradingCalendar.trading_date <= date(year, 12, 31))
            .all()
        }
    written = 0
    nav_url = f'https://fundf10.eastmoney.com/f10/jjjz_{fund_code}.html'
    price_url = f'https://gu.qq.com/{_market_for_code(fund_code)}{fund_code}/gp'
    for trading_day in sorted(set(navs).intersection(closes).intersection(calendar_days)):
        if upsert_observation(
            fund_code=fund_code, trading_date=trading_day, close_price=closes[trading_day],
            unit_nav=navs[trading_day], price_source=_TENCENT_KLINE_SOURCE,
            price_source_url=price_url, nav_source=_EM_NAV_SOURCE, nav_source_url=nav_url,
            nav_date=trading_day, captured_by='backfill',
        ):
            written += 1
    return written


@contextmanager
def _job_lock(job_key):
    """PostgreSQL advisory lock 和任务行共同提供跨进程排他与可恢复状态。"""
    db = SessionLocal()
    acquired = False
    try:
        if db.bind.dialect.name == 'postgresql':
            acquired = bool(db.execute(text('SELECT pg_try_advisory_lock(hashtext(:key))'), {'key': job_key}).scalar())
        else:
            existing = db.query(LofPremiumJob).filter_by(job_key=job_key).one_or_none()
            acquired = not existing or existing.status != 'running'
        if not acquired:
            yield None
            return
        job = db.query(LofPremiumJob).filter_by(job_key=job_key).one_or_none()
        if job is None:
            job = LofPremiumJob(job_key=job_key)
            db.add(job)
        job.resume_cursor = job.cursor if job.status in {'running', 'failed'} else None
        job.status = 'running'
        job.attempts += 1
        job.started_at = datetime.now(_CST)
        job.last_error = None
        db.commit()
        yield job
        job.status = 'completed'
        job.completed_at = datetime.now(_CST)
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.query(LofPremiumJob).filter_by(job_key=job_key).one_or_none()
        if job:
            job.status = 'failed'
            job.last_error = str(exc)[:4000]
            db.commit()
        raise
    finally:
        if acquired and db.bind.dialect.name == 'postgresql':
            db.execute(text('SELECT pg_advisory_unlock(hashtext(:key))'), {'key': job_key})
            db.commit()
        db.close()


def backfill_year(fund_codes, year):
    job_key = f'backfill:{year}'
    with _job_lock(job_key) as job:
        if job is None:
            return {'status': 'already_running', 'processed': 0, 'observations': 0}
        codes = sorted(set(str(code) for code in fund_codes if code))
        start = codes.index(job.resume_cursor) + 1 if job.resume_cursor in codes else 0
        processed = observations = 0
        for code in codes[start:]:
            observations += backfill_fund(code, year)
            processed += 1
            job.cursor = code
            with get_db_session() as db:
                stored = db.query(LofPremiumJob).filter_by(job_key=job_key).one()
                stored.cursor = code
        return {'status': 'completed', 'processed': processed, 'observations': observations}


def capture_day(fund_codes, trading_day=None):
    capture_date = trading_day or datetime.now(_CST).date()
    now = datetime.now(_CST)
    if trading_day is None and (now.hour < 20 or now.hour > 23 or (now.hour == 20 and now.minute < 30)):
        return {'status': 'outside_capture_window', 'observations': 0}
    with _job_lock(f'capture:{capture_date.isoformat()}') as job:
        if job is None:
            return {'status': 'already_running', 'observations': 0}
        with get_db_session() as db:
            is_trading_day = db.get(TradingCalendar, capture_date) is not None
        if not is_trading_day:
            return {'status': 'not_trading_day', 'observations': 0}
        observations = 0
        for code in fund_codes:
            navs = fetch_nav_history(code, capture_date.year)
            closes = fetch_close_history(code, capture_date.year)
            if capture_date not in navs or capture_date not in closes:
                continue
            observations += int(upsert_observation(
                fund_code=code, trading_date=capture_date, close_price=closes[capture_date],
                unit_nav=navs[capture_date], price_source=_TENCENT_KLINE_SOURCE,
                price_source_url=f'https://gu.qq.com/{_market_for_code(code)}{code}/gp',
                nav_source=_EM_NAV_SOURCE,
                nav_source_url=f'https://fundf10.eastmoney.com/f10/jjjz_{code}.html',
                nav_date=capture_date, captured_by='capture',
            ))
        return {'status': 'completed', 'observations': observations}
