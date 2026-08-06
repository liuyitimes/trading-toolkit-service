# -*- coding: utf-8 -*-
"""LOF 溢价日度观测持久化与连续正溢价计算。

事实来源：
- A 股交易日历来自沪深交易所官方休市安排（trading_calendar）；
- 日度观测来自东方财富历史单位净值（lsjz）与腾讯日 K 线的同日配对；
- 回补与采集任务通过 lof_premium_job 记录进度，并使用数据库互斥锁保证
  同类任务不并发运行。

读取接口只消费本模块的计算结果；观测写入失败不得以缓存、零值或推断替代。
"""

import json
import logging
import threading
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select, text

from models.database import SessionLocal, engine
from models.lof_premium import LofPremiumJob, LofPremiumObservation, TradingCalendar
from services.http_client import em_get, tencent_get
from utils.convert import safe_float

logger = logging.getLogger('trading_toolkit')

_CHINA_TZ = ZoneInfo('Asia/Shanghai')
_NAV_URL = 'https://api.fund.eastmoney.com/f10/lsjz'
_KLINE_URL = 'https://ifzq.gtimg.cn/appstock/app/kline/kline'
_NAV_REFERER = 'https://fundf10.eastmoney.com/'
_CALENDAR_DIR = Path(__file__).resolve().parents[1] / 'data' / 'trading_calendar'
_BACKFILL_PAGE_SIZE = 50
_BACKFILL_MAX_PAGES = 30
_KLINE_YEAR_LIMIT = 320
_SQLITE_LOCKS = {}
_SQLITE_LOCKS_GUARD = threading.Lock()


def _now():
    return datetime.now(_CHINA_TZ)


def _today():
    return _now().date()


def _db_name():
    return engine.dialect.name


def _is_postgres():
    return _db_name() == 'postgresql'


def _sqlite_lock(key):
    with _SQLITE_LOCKS_GUARD:
        lock = _SQLITE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _SQLITE_LOCKS[key] = lock
        return lock


# ==================== 交易日历 ====================


def load_calendar_seed(year):
    """读取官方休市安排种子文件，返回 {year, source, holidays}。"""
    seed_file = _CALENDAR_DIR / f'{year}.json'
    with seed_file.open('r', encoding='utf-8') as source_file:
        return json.load(source_file)


def import_calendar_year(db, year, source_url=None, source_version=None, holidays=None):
    """导入某一年全部自然日的开市标识，替换该年既有记录。"""
    seed = load_calendar_seed(year)
    holidays = set(str(day) for day in (holidays or seed.get('holidays') or []))
    source_url = source_url or (seed.get('source') or {}).get('url', '')
    source_version = source_version or (seed.get('source') or {}).get('version', '')

    db.execute(
        text('DELETE FROM trading_calendar WHERE calendar_date BETWEEN :start AND :end'),
        {'start': f'{year}-01-01', 'end': f'{year}-12-31'},
    )
    start = date(year, 1, 1)
    end = date(year, 12, 31)
    cursor = start
    while cursor <= end:
        is_trading = cursor.weekday() < 5 and cursor.isoformat() not in holidays
        db.add(
            TradingCalendar(
                calendar_date=cursor,
                is_trading_day=is_trading,
                source_url=source_url,
                source_version=source_version,
            )
        )
        cursor += timedelta(days=1)
    db.flush()
    return {
        'year': year,
        'holidays': sorted(holidays),
        'source_url': source_url,
        'source_version': source_version,
    }


def is_trading_day(db, target_date):
    """日历表缺失的日期一律视为非开市日，不推断。"""
    row = db.execute(
        select(TradingCalendar).where(TradingCalendar.calendar_date == target_date)
    ).scalar_one_or_none()
    return bool(row and row.is_trading_day)


def trading_days_between(db, start, end):
    """返回 [start, end] 内按升序排列的开市日。"""
    rows = db.execute(
        select(TradingCalendar.calendar_date)
        .where(
            TradingCalendar.calendar_date >= start,
            TradingCalendar.calendar_date <= end,
            TradingCalendar.is_trading_day.is_(True),
        )
        .order_by(TradingCalendar.calendar_date.asc())
    ).scalars().all()
    return list(rows)


def latest_trading_day(db, as_of=None):
    """返回 as_of 当天或之前最近的开市日；无记录时返回 None。"""
    as_of = as_of or _today()
    row = db.execute(
        select(TradingCalendar.calendar_date)
        .where(
            TradingCalendar.calendar_date <= as_of,
            TradingCalendar.is_trading_day.is_(True),
        )
        .order_by(TradingCalendar.calendar_date.desc())
    ).scalars().first()
    return row


# ==================== 观测写入与读取 ====================


def upsert_observation(
    db,
    fund_code,
    trading_date,
    close_price,
    unit_nav,
    price_source,
    price_source_url,
    nav_source,
    nav_source_url,
    nav_published_date,
    write_source,
):
    """同一基金、同一交易日的可审计幂等更新；修订保留首次观测时间并提升版本。"""
    close_price = safe_float(close_price)
    unit_nav = safe_float(unit_nav)
    if close_price <= 0 or unit_nav <= 0:
        return None
    premium_rate = round((close_price / unit_nav - 1) * 100, 4)

    row = db.execute(
        select(LofPremiumObservation).where(
            LofPremiumObservation.fund_code == fund_code,
            LofPremiumObservation.trading_date == trading_date,
        )
    ).scalar_one_or_none()

    if row is None:
        row = LofPremiumObservation(
            fund_code=fund_code,
            trading_date=trading_date,
            close_price=close_price,
            unit_nav=unit_nav,
            premium_rate=premium_rate,
            price_source=price_source,
            price_source_url=price_source_url,
            nav_source=nav_source,
            nav_source_url=nav_source_url,
            nav_published_date=nav_published_date,
            write_source=write_source,
            version=1,
            observed_at=_now(),
        )
        db.add(row)
    else:
        row.close_price = close_price
        row.unit_nav = unit_nav
        row.premium_rate = premium_rate
        row.price_source = price_source
        row.price_source_url = price_source_url
        row.nav_source = nav_source
        row.nav_source_url = nav_source_url
        row.nav_published_date = nav_published_date
        row.write_source = write_source
        row.version = (row.version or 1) + 1
    db.flush()
    return {
        'fund_code': fund_code,
        'trading_date': trading_date.isoformat(),
        'premium_rate': premium_rate,
        'version': row.version,
    }


def observations_for_funds(db, fund_codes, start, end):
    """批量读取区间内观测，返回 {fund_code: {trading_date: observation}}。"""
    codes = [str(code) for code in (fund_codes or []) if str(code)]
    if not codes:
        return {}
    rows = db.execute(
        select(LofPremiumObservation).where(
            LofPremiumObservation.fund_code.in_(codes),
            LofPremiumObservation.trading_date >= start,
            LofPremiumObservation.trading_date <= end,
        )
    ).scalars().all()
    grouped = {}
    for row in rows:
        grouped.setdefault(row.fund_code, {})[row.trading_date] = row
    return grouped


def latest_nav_dates(db, fund_codes, as_of=None):
    """返回每只基金最近观测的实际净值日期（用于实时列表，不伪造行情时间）。"""
    as_of = as_of or _today()
    start = date(as_of.year - 1, 1, 1)
    grouped = observations_for_funds(db, fund_codes, start, as_of)
    result = {}
    for code, by_day in grouped.items():
        latest_day = max(by_day)
        row = by_day[latest_day]
        result[code] = {
            'nav_date': row.nav_published_date.isoformat() if row.nav_published_date else None,
            'unit_nav': row.unit_nav,
            'trading_date': latest_day.isoformat(),
        }
    return result


# ==================== 连续正溢价计算 ====================


def _unavailable(reason, as_of):
    return {
        'consecutive_positive_sessions': None,
        'status': 'unavailable',
        'as_of': as_of.isoformat(),
        'history_started_on': None,
        'reason': reason,
    }


def compute_premium_persistence(db, fund_code, as_of=None):
    """计算单只 LOF 的连续正溢价持续性。"""
    return compute_premium_persistence_batch(db, [fund_code], as_of=as_of).get(str(fund_code))


def compute_premium_persistence_batch(db, fund_codes, as_of=None):
    """批量计算连续正溢价，避免列表读取路径逐只查询。"""
    as_of = as_of or _today()
    latest_day = latest_trading_day(db, as_of)
    if latest_day is None:
        return {
            str(code): _unavailable('交易日历未导入或未覆盖当前日期', as_of)
            for code in fund_codes
            if str(code)
        }

    # 回补与采集的覆盖下界取当前自然年首个交易日；更早历史不可由首次导入推断。
    year_start_trading_day = trading_days_between(db, date(as_of.year, 1, 1), latest_day)
    if not year_start_trading_day:
        return {
            str(code): _unavailable('当前自然年无已导入交易日', as_of)
            for code in fund_codes
            if str(code)
        }
    range_start = year_start_trading_day[0]
    trading_days_desc = list(reversed(year_start_trading_day))

    codes = [str(code) for code in fund_codes if str(code)]
    grouped = observations_for_funds(db, codes, range_start, latest_day)
    result = {}
    for code in codes:
        by_day = grouped.get(code, {})
        latest_obs = by_day.get(latest_day)
        if latest_obs is None:
            result[code] = _unavailable(
                f'当前交易日 {latest_day.isoformat()} 无同日可比观测',
                as_of,
            )
            continue

        if latest_obs.premium_rate <= 0:
            result[code] = {
                'consecutive_positive_sessions': 0,
                'status': 'complete',
                'as_of': latest_day.isoformat(),
                'history_started_on': None,
                'reason': None,
            }
            continue

        count = 1
        history_started_on = None
        reason = None
        status = 'complete'
        for cursor in trading_days_desc[1:]:
            prev_obs = by_day.get(cursor)
            if prev_obs is None:
                if cursor == range_start:
                    status = 'partial'
                    history_started_on = range_start.isoformat()
                    reason = f'历史覆盖不足：最早覆盖日为 {range_start.isoformat()}'
                else:
                    status = 'partial'
                    reason = f'历史缺口：{cursor.isoformat()} 缺少同日可比观测'
                break
            if prev_obs.premium_rate <= 0:
                status = 'complete'
                break
            count += 1
        else:
            status = 'partial'
            history_started_on = range_start.isoformat()
            reason = f'历史覆盖不足：最早覆盖日为 {range_start.isoformat()}'

        result[code] = {
            'consecutive_positive_sessions': count,
            'status': status,
            'as_of': latest_day.isoformat(),
            'history_started_on': history_started_on,
            'reason': reason,
        }
    return result


# ==================== 上游数据获取 ====================


def _market_symbol(code):
    code = str(code or '').strip()
    if not code:
        return ''
    return f'sh{code}' if code.startswith('5') else f'sz{code}'


def fetch_em_nav_history(fund_code, start_date, end_date):
    """东方财富历史单位净值（lsjz），按净值日期升序返回。"""
    nav_rows = []
    page = 1
    while page <= _BACKFILL_MAX_PAGES:
        try:
            resp = em_get(
                _NAV_URL,
                params={
                    'fundCode': fund_code,
                    'pageIndex': page,
                    'pageSize': _BACKFILL_PAGE_SIZE,
                    'startDate': start_date.isoformat(),
                    'endDate': end_date.isoformat(),
                },
                headers={'Referer': _NAV_REFERER},
                timeout=10,
            )
            if resp.status_code != 200:
                logger.warning('[LOF观察] %s 净值 HTTP %s', fund_code, resp.status_code)
                break
            entries = (resp.json().get('Data') or {}).get('LSJZList') or []
            if not entries:
                break
            for entry in entries:
                nav_date = str(entry.get('FSRQ') or '')[:10]
                nav = safe_float(entry.get('DWJZ', 0))
                if nav_date and nav > 0:
                    nav_rows.append({'date': nav_date, 'nav': nav})
            if len(entries) < _BACKFILL_PAGE_SIZE:
                break
            page += 1
        except Exception as exc:
            logger.warning('[LOF观察] %s 历史净值获取失败: %s', fund_code, exc)
            break
    nav_rows.sort(key=lambda item: item['date'])
    return nav_rows


def fetch_tencent_kline_daily(fund_code, start_date, end_date, as_of=None):
    """腾讯日 K 线收盘价，过滤到目标区间且不包含 as_of 当日未收盘数据。"""
    symbol = _market_symbol(fund_code)
    if not symbol:
        return []
    as_of = as_of or _today()
    try:
        resp = tencent_get(
            _KLINE_URL,
            params={'param': f'{symbol},day,,,{_KLINE_YEAR_LIMIT}'},
            timeout=10,
        )
        if resp.status_code != 200:
            return []
        day_rows = ((resp.json().get('data') or {}).get(symbol) or {}).get('day') or []
        result = []
        for point in day_rows:
            if len(point) < 3:
                continue
            trade_date = str(point[0]).split(' ')[0]
            close = safe_float(point[2])
            if (
                not trade_date
                or close <= 0
                or trade_date < start_date.isoformat()
                or trade_date > end_date.isoformat()
                or trade_date >= as_of.isoformat()
            ):
                continue
            result.append({'date': trade_date, 'close': close})
        result.sort(key=lambda item: item['date'])
        return result
    except Exception as exc:
        logger.warning('[LOF观察] %s 日 K 线获取失败: %s', fund_code, exc)
        return []


# ==================== 任务进度与互斥 ====================


def _job_key(job_type, scope_year):
    return f'{job_type}:{scope_year or ""}'


def acquire_job(db, job_type, scope_year=None):
    """创建或取回任务行；返回 None 表示同类任务已在运行或不可用。"""
    job = db.execute(
        select(LofPremiumJob).where(
            LofPremiumJob.job_type == job_type,
            LofPremiumJob.scope_year == scope_year,
        )
    ).scalar_one_or_none()
    if job is None:
        job = LofPremiumJob(job_type=job_type, scope_year=scope_year, status='pending')
        db.add(job)
        db.flush()

    key = _job_key(job_type, scope_year)
    if _is_postgres():
        acquired = db.execute(
            text('SELECT pg_try_advisory_lock(:key)'),
            {'key': hash(key) & 0x7FFFFFFF},
        ).scalar()
        if not acquired:
            return None
    else:
        lock = _sqlite_lock(key)
        if not lock.acquire(blocking=False):
            return None

    if job.status == 'running':
        _release_job(db, key)
        return None
    job.status = 'running'
    job.attempt_count = (job.attempt_count or 0) + 1
    job.started_at = _now()
    job.completed_at = None
    job.last_error = None
    db.flush()
    db.commit()
    return job


def _release_job(db, key):
    if _is_postgres():
        db.execute(
            text('SELECT pg_advisory_unlock(:key)'),
            {'key': hash(key) & 0x7FFFFFFF},
        )
    else:
        _sqlite_lock(key).release()


def finish_job(db, job, status='succeeded', error=None, success_count=0, failure_count=0):
    if job is None:
        return
    job.status = status
    job.completed_at = _now()
    job.last_error = (error or '')[:2000] or None
    job.success_count = success_count
    job.failure_count = failure_count
    key = _job_key(job.job_type, job.scope_year)
    db.flush()
    _release_job(db, key)


# ==================== 回补与日度采集 ====================


def run_backfill(db, year=None, fund_codes=None, as_of=None):
    """当前自然年历史回补：东方财富净值与腾讯收盘价按同日配对写入观测。"""
    as_of = as_of or _today()
    year = year or as_of.year
    job = acquire_job(db, 'backfill', year)
    if job is None:
        return {'acquired': False}

    success_count = 0
    failure_count = 0
    try:
        trading_days = trading_days_between(db, date(year, 1, 1), as_of)
        if not trading_days:
            raise RuntimeError('交易日历未导入，无法回补')
        day_set = {day.isoformat() for day in trading_days}

        if fund_codes is None:
            from services.lof_fund import _fetch_em_lof_rows

            fund_codes = [str(row.get('f12') or '') for row in _fetch_em_lof_rows()]
        fund_codes = [code for code in fund_codes if str(code).strip()]

        cursor_state = {}
        if job.cursor:
            try:
                cursor_state = json.loads(job.cursor)
            except (TypeError, json.JSONDecodeError):
                cursor_state = {}
        start_index = int(cursor_state.get('next_index', 0))

        for index in range(start_index, len(fund_codes)):
            code = str(fund_codes[index]).strip()
            if not code:
                continue
            try:
                nav_rows = fetch_em_nav_history(code, date(year, 1, 1), as_of)
                nav_by_day = {row['date']: row['nav'] for row in nav_rows}
                close_rows = fetch_tencent_kline_daily(code, date(year, 1, 1), as_of, as_of=as_of)
                close_by_day = {row['date']: row['close'] for row in close_rows}
                written = 0
                for day in day_set:
                    if day not in nav_by_day or day not in close_by_day:
                        continue
                    upsert_observation(
                        db,
                        code,
                        date.fromisoformat(day),
                        close_by_day[day],
                        nav_by_day[day],
                        price_source='腾讯日K线',
                        price_source_url=_KLINE_URL,
                        nav_source='东方财富历史单位净值',
                        nav_source_url=_NAV_URL,
                        nav_published_date=date.fromisoformat(day),
                        write_source='backfill',
                    )
                    written += 1
                success_count += 1
                job.cursor = json.dumps({'next_index': index + 1}, ensure_ascii=False)
                job.success_count = success_count
                db.flush()
                if written == 0:
                    logger.info('[LOF观察] %s 回补无同日可配对观测', code)
                if (index + 1) % 10 == 0:
                    db.commit()
            except Exception as exc:
                db.rollback()
                failure_count += 1
                job = db.execute(
                    select(LofPremiumJob).where(
                        LofPremiumJob.job_type == 'backfill',
                        LofPremiumJob.scope_year == year,
                    )
                ).scalar_one()
                job.failure_count = failure_count
                job.last_error = f'{code}: {exc}'[:2000]
                logger.warning('[LOF观察] %s 回补失败: %s', code, exc)
                db.flush()

        finish_job(
            db,
            job,
            status='succeeded',
            success_count=success_count,
            failure_count=failure_count,
        )
        db.commit()
        return {
            'acquired': True,
            'year': year,
            'success_count': success_count,
            'failure_count': failure_count,
        }
    except Exception as exc:
        finish_job(db, job, status='failed', error=str(exc), success_count=success_count, failure_count=failure_count)
        db.commit()
        logger.warning('[LOF观察] 回补任务失败: %s', exc)
        return {'acquired': True, 'error': str(exc)}


def run_daily_capture(db, as_of=None):
    """收盘后日度采集：仅写入当日已有同日可比净值与价格的观测。"""
    as_of = as_of or _today()
    year = as_of.year
    job = acquire_job(db, 'daily_capture', year)
    if job is None:
        return {'acquired': False}

    success_count = 0
    failure_count = 0
    try:
        latest_day = latest_trading_day(db, as_of)
        if latest_day is None:
            raise RuntimeError('交易日历未导入，无法采集')
        if latest_day != as_of:
            finish_job(
                db,
                job,
                status='succeeded',
                success_count=0,
                failure_count=0,
            )
            db.commit()
            return {'acquired': True, 'skipped': '当前日期非交易日', 'latest_trading_day': latest_day.isoformat()}

        from services.lof_fund import _fetch_em_lof_rows, _fetch_tencent_quotes

        universe = _fetch_em_lof_rows()
        quotes = _fetch_tencent_quotes(universe)
        written = 0
        pending = 0
        for row in universe:
            code = str(row.get('f12') or '')
            quote_values = quotes.get(code)
            if not code or not quote_values:
                continue
            try:
                price = safe_float(quote_values[3] if len(quote_values) > 3 else 0)
                if price <= 0:
                    continue
                nav_rows = fetch_em_nav_history(code, as_of, as_of)
                latest_nav = nav_rows[-1] if nav_rows else None
                if not latest_nav or latest_nav['date'] != as_of.isoformat():
                    pending += 1
                    continue
                upsert_observation(
                    db,
                    code,
                    as_of,
                    price,
                    latest_nav['nav'],
                    price_source='腾讯实时行情',
                    price_source_url='https://qt.gtimg.cn/q=',
                    nav_source='东方财富历史单位净值',
                    nav_source_url=_NAV_URL,
                    nav_published_date=as_of,
                    write_source='scheduled_capture',
                )
                written += 1
                success_count += 1
                db.flush()
                if written % 10 == 0:
                    db.commit()
            except Exception as exc:
                db.rollback()
                failure_count += 1
                logger.warning('[LOF观察] %s 日度采集失败: %s', code, exc)
                job = db.execute(
                    select(LofPremiumJob).where(
                        LofPremiumJob.job_type == 'daily_capture',
                        LofPremiumJob.scope_year == year,
                    )
                ).scalar_one()
                job.failure_count = failure_count
                db.flush()
        finish_job(
            db,
            job,
            status='succeeded',
            success_count=success_count,
            failure_count=failure_count,
        )
        db.commit()
        return {
            'acquired': True,
            'written': written,
            'pending_nav': pending,
            'latest_trading_day': latest_day.isoformat(),
        }
    except Exception as exc:
        finish_job(db, job, status='failed', error=str(exc), success_count=success_count, failure_count=failure_count)
        db.commit()
        logger.warning('[LOF观察] 日度采集失败: %s', exc)
        return {'acquired': True, 'error': str(exc)}
