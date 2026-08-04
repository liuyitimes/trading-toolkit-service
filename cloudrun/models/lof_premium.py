# -*- coding: utf-8 -*-
"""LOF 溢价日度观测、交易日历和任务进度模型。"""

from sqlalchemy import Column, Date, DateTime, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from models.database import Base


class TradingCalendar(Base):
    __tablename__ = 'trading_calendar'

    trading_date = Column(Date, primary_key=True)
    market = Column(String(20), nullable=False, default='cn-a')
    source = Column(String(100), nullable=False)
    source_version = Column(String(100), nullable=True)
    imported_at = Column(DateTime, nullable=False, server_default=func.now())


class LofPremiumObservation(Base):
    __tablename__ = 'lof_premium_observation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    close_price = Column(Numeric(18, 6), nullable=False)
    unit_nav = Column(Numeric(18, 6), nullable=False)
    premium_rate = Column(Numeric(12, 6), nullable=False)
    price_source = Column(String(100), nullable=False)
    price_source_url = Column(String(1000), nullable=True)
    nav_source = Column(String(100), nullable=False)
    nav_source_url = Column(String(1000), nullable=True)
    nav_date = Column(Date, nullable=False)
    captured_by = Column(String(20), nullable=False, default='capture')
    source_version = Column(Integer, nullable=False, default=1)
    observed_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('fund_code', 'trading_date', name='uq_lof_premium_observation_fund_date'),
    )


class LofPremiumJob(Base):
    __tablename__ = 'lof_premium_job'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_key = Column(String(100), nullable=False, unique=True)
    status = Column(String(20), nullable=False, default='queued', index=True)
    cursor = Column(String(100), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
