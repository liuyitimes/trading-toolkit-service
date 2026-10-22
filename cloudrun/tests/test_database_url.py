# -*- coding: utf-8 -*-
"""数据库连接串驱动程序回归测试。

覆盖 2026-10-22 线上发布故障：SQLAlchemy 2.1 将 ``postgresql://`` 的默认 DBAPI
改为 psycopg（v3），而镜像只提供 psycopg2-binary，导致容器启动阶段的
``alembic upgrade head`` 直接抛 ModuleNotFoundError。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

SERVICE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE_ROOT))

from utils.dburl import describe_driver, is_postgresql, normalize_database_url  # noqa: E402


def test_platform_url_gets_explicit_psycopg2_driver():
    """托管平台注入的无驱动名 URL 必须补齐 psycopg2。"""
    normalized = normalize_database_url(
        'postgresql://user:secret@db.internal:5432/trading_toolkit'
    )
    assert normalized == (
        'postgresql+psycopg2://user:secret@db.internal:5432/trading_toolkit'
    )
    assert describe_driver(normalized) == 'psycopg2'


def test_postgres_alias_is_normalized():
    """Render / Heroku 的历史别名 postgres:// 同样要补齐驱动名。"""
    assert normalize_database_url('postgres://u:p@h/db') == (
        'postgresql+psycopg2://u:p@h/db'
    )


def test_explicit_driver_is_preserved():
    """调用方显式声明的驱动不被覆盖。"""
    explicit = 'postgresql+psycopg://u:p@h/db'
    assert normalize_database_url(explicit) == explicit


def test_sqlite_url_is_untouched():
    """SQLite 连接串与无协议相对路径保持原样。"""
    assert normalize_database_url('sqlite:///trading_toolkit.db') == (
        'sqlite:///trading_toolkit.db'
    )
    assert normalize_database_url('trading_toolkit.db') == 'trading_toolkit.db'


def test_credentials_with_special_characters_survive():
    """归一化只改协议前缀，不能破坏已编码的账号密码或查询参数。"""
    url = 'postgresql://app%40corp:p%3Ass%2Fword@db:5432/x?sslmode=require'
    normalized = normalize_database_url(url)
    assert normalized.startswith('postgresql+psycopg2://')
    assert 'app%40corp:p%3Ass%2Fword@db:5432/x?sslmode=require' in normalized


def test_empty_url_is_rejected():
    with pytest.raises(ValueError):
        normalize_database_url('')


@pytest.mark.parametrize(
    ('url', 'expected'),
    [
        ('postgresql://u:p@h/db', True),
        ('postgres://u:p@h/db', True),
        ('postgresql+psycopg2://u:p@h/db', True),
        ('sqlite:///x.db', False),
        ('mysql://u:p@h/db', False),
    ],
)
def test_is_postgresql(url, expected):
    assert is_postgresql(url) is expected


def test_engine_uses_psycopg2_for_platform_url():
    """核心回归：模块级引擎必须以 psycopg2 方言构建，而不是 psycopg v3。

    在子进程中执行，避免污染其他用例已经绑定的 SQLite 引擎。
    """
    env = dict(os.environ)
    env['DATABASE_URL'] = 'postgresql://user:secret@127.0.0.1:5432/trading_toolkit'
    completed = subprocess.run(
        [
            sys.executable,
            '-c',
            'import models.database as d; print(d.engine.dialect.driver)',
        ],
        cwd=str(SERVICE_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == 'psycopg2'
