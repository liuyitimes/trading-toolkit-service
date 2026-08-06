#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""LOF 溢价观测的可移植任务命令（由外部调度器调用）。

用法（在 cloudrun/ 目录下）：
    python cli.py calendar-import --year 2026
    python cli.py backfill --year 2026
    python cli.py capture
    python cli.py status

任务本身不承载调度；Ubuntu 使用 systemd timer（见 systemd/ 示例），
其他平台使用 Cron 在交易日 20:30-23:30（中国标准时间）调用。
"""

import json
import sys
from datetime import datetime

import click
from sqlalchemy import func, select, text

import models  # noqa: F401  确保 Base.metadata 已注册全部模型
from models.database import SessionLocal, init_db
from models.lof_premium import LofPremiumJob, TradingCalendar
from services import lof_premium_persistence as persistence


@click.group()
def cli():
    """LOF 溢价观测任务命令。"""


@cli.command('calendar-import')
@click.option('--year', type=int, required=True, help='要导入的年份')
def calendar_import(year):
    """按官方休市安排导入指定年份的 A 股交易日历。"""
    init_db()
    with SessionLocal() as db:
        summary = persistence.import_calendar_year(db, year)
        db.commit()
    click.echo(json.dumps(summary, ensure_ascii=False))


@cli.command('backfill')
@click.option('--year', type=int, default=None, help='回补年份，默认当前自然年')
@click.option('--fund', 'fund_codes', multiple=True, help='仅回补指定基金，可多次传入')
def backfill(year, fund_codes):
    """执行当前自然年历史回补（东方财富净值与腾讯收盘价同日配对）。"""
    init_db()
    with SessionLocal() as db:
        result = persistence.run_backfill(
            db,
            year=year,
            fund_codes=list(fund_codes) or None,
        )
    click.echo(json.dumps(result, ensure_ascii=False))


@cli.command('capture')
def capture():
    """执行收盘后日度采集（仅在当日为交易日且已有同日可比净值时写入）。"""
    init_db()
    with SessionLocal() as db:
        result = persistence.run_daily_capture(db)
    click.echo(json.dumps(result, ensure_ascii=False))


@cli.command('status')
def status():
    """展示日历、观测与任务状态。"""
    init_db()
    with SessionLocal() as db:
        calendar_days = db.execute(
            select(func.count()).select_from(TradingCalendar)
        ).scalar() or 0
        trading_days = db.execute(
            select(func.count())
            .select_from(TradingCalendar)
            .where(TradingCalendar.is_trading_day.is_(True))
        ).scalar() or 0
        observation_rows = db.execute(
            select(func.count()).select_from(text('lof_premium_observation'))
        ).scalar() or 0
        jobs = db.execute(
            select(LofPremiumJob).order_by(LofPremiumJob.created_at.desc())
        ).scalars().all()
        click.echo(
            json.dumps(
                {
                    'calendar_days': calendar_days,
                    'trading_days': trading_days,
                    'observations': observation_rows,
                    'jobs': [
                        {
                            'job_type': job.job_type,
                            'scope_year': job.scope_year,
                            'status': job.status,
                            'attempt_count': job.attempt_count,
                            'success_count': job.success_count,
                            'failure_count': job.failure_count,
                            'started_at': (
                                job.started_at.isoformat() if job.started_at else None
                            ),
                            'completed_at': (
                                job.completed_at.isoformat() if job.completed_at else None
                            ),
                        }
                        for job in jobs
                    ],
                },
                ensure_ascii=False,
            )
        )


if __name__ == '__main__':
    cli()
