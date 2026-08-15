# -*- coding: utf-8 -*-
"""LOF 溢价日度观测持久化模型。

本模块承载 LOF 连续正溢价的唯一事实来源：
- trading_calendar：沪深交易所官方休市安排导入的 A 股交易日历；
- lof_premium_observation：同一基金、同一交易日的可审计日度观测；
- lof_premium_job：回补与日度采集任务的可恢复进度。

观测写入失败不得由缓存、零值或推断值替代；读取路径只消费已持久化事实。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from models.database import Base


class TradingCalendar(Base):
    """A 股交易日历（沪深交易所共同开市日）。"""

    __tablename__ = 'trading_calendar'

    id = Column(Integer, primary_key=True, autoincrement=True)
    calendar_date = Column(Date, nullable=False, unique=True, index=True)
    is_trading_day = Column(Boolean, nullable=False, default=False)
    source_url = Column(String(500), nullable=False)
    source_version = Column(String(100), nullable=False)
    imported_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('calendar_date', name='uq_trading_calendar_date'),
    )


class LofPremiumObservation(Base):
    """LOF 溢价日度观测：价格与已公布单位净值同日配对的审计记录。"""

    __tablename__ = 'lof_premium_observation'

    id = Column(Integer, primary_key=True, autoincrement=True)
    fund_code = Column(String(20), nullable=False, index=True)
    trading_date = Column(Date, nullable=False, index=True)
    close_price = Column(Float, nullable=False)
    unit_nav = Column(Float, nullable=False)
    premium_rate = Column(Float, nullable=False)
    price_source = Column(String(50), nullable=False)
    price_source_url = Column(String(500), nullable=True)
    nav_source = Column(String(50), nullable=False)
    nav_source_url = Column(String(500), nullable=True)
    nav_published_date = Column(Date, nullable=True)
    write_source = Column(String(30), nullable=False, server_default='scheduled_capture')
    version = Column(Integer, nullable=False, server_default='1')
    observed_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('fund_code', 'trading_date', name='uq_lof_premium_observation'),
    )


class LofPremiumJob(Base):
    """回补与日度采集任务的可恢复进度。"""

    __tablename__ = 'lof_premium_job'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_type = Column(String(30), nullable=False)
    scope_year = Column(Integer, nullable=True)
    status = Column(String(20), nullable=False, server_default='pending')
    cursor = Column(Text, nullable=True)
    attempt_count = Column(Integer, nullable=False, server_default='0')
    success_count = Column(Integer, nullable=False, server_default='0')
    failure_count = Column(Integer, nullable=False, server_default='0')
    last_error = Column(Text, nullable=True)
    next_retry_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('job_type', 'scope_year', name='uq_lof_premium_job'),
    )
