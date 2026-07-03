# -*- coding: utf-8 -*-
"""用户相关数据模型"""

from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, UniqueConstraint
from sqlalchemy.sql import func
from models.database import Base


class UserFavorite(Base):
    """用户自选"""
    __tablename__ = 'user_favorites'

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=False, index=True)
    code = Column(String(20), nullable=False)         # 证券代码
    name = Column(String(50), nullable=False)          # 证券名称
    type = Column(String(20), nullable=False)          # bond / lof / hkipo
    price = Column(Float, nullable=True)               # 添加时的价格
    premium_rate = Column(Float, nullable=True)        # 添加时的溢价率
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('openid', 'code', 'type', name='uq_user_fav'),
    )


class UserReminder(Base):
    """用户提醒"""
    __tablename__ = 'user_reminders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=False, index=True)
    code = Column(String(20), nullable=False)
    name = Column(String(50), nullable=False)
    type = Column(String(20), nullable=False)          # bond / lof / hkipo
    remind_type = Column(String(20), nullable=False)   # subscribe / price / draw
    remind_value = Column(String(100), nullable=True)  # 提醒条件值
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint('openid', 'code', 'type', 'remind_type', name='uq_user_reminder'),
    )


class UserSetting(Base):
    """用户设置"""
    __tablename__ = 'user_settings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(String(64), nullable=False, unique=True)
    theme = Column(String(10), default='light')        # light / dark
    default_tab = Column(String(20), default='market')  # market / convertible / lof / hkipo
    remind_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
