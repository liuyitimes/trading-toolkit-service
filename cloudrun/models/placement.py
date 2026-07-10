# -*- coding: utf-8 -*-
"""配售结果数据模型 — 存储从交易所公告中提取的配售/认购数据"""

from sqlalchemy import Column, Integer, String, DateTime, Float, UniqueConstraint
from sqlalchemy.sql import func
from models.database import Base


class PlacementResult(Base):
    """配售/认购结果（来源：巨潮资讯公告）"""
    __tablename__ = 'placement_result'

    id = Column(Integer, primary_key=True, autoincrement=True)
    stock_code = Column(String(20), nullable=False, index=True)   # 股票代码
    stock_name = Column(String(50), nullable=False)                # 股票名称
    bond_code = Column(String(20), nullable=True)                  # 转债代码（可转债专用）
    bond_name = Column(String(50), nullable=True)                  # 转债名称（可转债专用）
    asset_type = Column(String(20), nullable=False)                # bond(可转债) / stock(配股)

    issue_size = Column(Float, nullable=True)                      # 发行规模（亿元）
    shareholder_amount = Column(Float, nullable=True)              # 原股东认购金额（亿元）
    shareholder_ratio = Column(Float, nullable=True)               # 原股东配售率/认配率（%）
    online_amount = Column(Float, nullable=True)                   # 网上公众认购金额（亿元）
    online_ratio = Column(Float, nullable=True)                    # 网上中签率（%）
    underwriter_amount = Column(Float, nullable=True)              # 主承销商包销金额（亿元）

    announce_date = Column(String(20), nullable=True)              # 公告日期 YYYY-MM-DD
    announcement_id = Column(String(30), nullable=True)            # 巨潮公告 ID（去重键）
    source_url = Column(String(500), nullable=True)                # 公告来源 URL

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint('announcement_id', name='uq_placement_announcement'),
    )
