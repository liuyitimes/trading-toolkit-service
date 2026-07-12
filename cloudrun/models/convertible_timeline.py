# -*- coding: utf-8 -*-
"""持久化可转债发行时间轴，避免在列表接口重复扫描历史公告。"""

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from models.database import Base


class ConvertibleTimeline(Base):
    __tablename__ = 'convertible_timeline'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)
    bond_code = Column(String(20), nullable=True)
    stage_dates = Column(Text, nullable=False, default='{}')
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('stock_code', name='uq_convertible_timeline_stock'),
    )
