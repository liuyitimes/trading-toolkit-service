# -*- coding: utf-8 -*-
"""数据库初始化模块

本地开发默认使用 SQLite，可通过环境变量 DATABASE_URL 切换为 PostgreSQL。
PostgreSQL 连接串格式: postgresql://用户名:密码@localhost:5432/trading_toolkit
"""

import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 默认 SQLite，可通过环境变量切换为 PostgreSQL
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///trading_toolkit.db')

# 根据数据库类型设置不同参数
if DATABASE_URL.startswith('postgresql'):
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )
else:
    engine = create_engine(DATABASE_URL, echo=False)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db_session():
    """数据库会话上下文管理器，确保异常时自动回滚、正常时自动关闭"""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """获取数据库会话（用于依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库（创建所有表）"""
    Base.metadata.create_all(bind=engine)
