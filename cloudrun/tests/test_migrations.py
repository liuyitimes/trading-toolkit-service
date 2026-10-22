# -*- coding: utf-8 -*-
"""迁移链完整性回归测试。

覆盖 2026-10-22 的发布阻断：两个功能分支各自从同一父修订派生了迁移，合并后出现
两个 head，容器启动固定执行 `alembic upgrade head` 因此直接报
"Multiple head revisions are present" 而拒绝启动。

这类问题在单测（只用 SQLite + create_all）里完全看不到，只能在迁移层拦：
1. 必须恰好一个 head；
2. 迁移目录里的每个修订都必须能从 head 反向遍历到（不得有孤立分支）；
3. 任意两张迁移不得创建同名表（否则串行执行必然 "table already exists"）。
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

SERVICE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SERVICE_ROOT / 'cloudrun'))

VERSIONS_DIR = SERVICE_ROOT / 'cloudrun' / 'migrations' / 'versions'
BASELINE_REVISION = '9c3cae4c1a70'
_REVISION_PATTERN = re.compile(r"^revision:\s*str\s*=\s*['\"]([^'\"]+)['\"]", re.M)
_CREATE_TABLE_PATTERN = re.compile(r"op\.create_table\(\s*['\"]([^'\"]+)")


@pytest.fixture(scope='module')
def script_directory():
    return ScriptDirectory.from_config(Config(str(SERVICE_ROOT / 'alembic.ini')))


def _declared_revisions():
    revisions = {}
    for path in sorted(VERSIONS_DIR.glob('*.py')):
        match = _REVISION_PATTERN.search(path.read_text(encoding='utf-8'))
        assert match, f'{path.name} 没有声明 revision'
        revisions[match.group(1)] = path.name
    return revisions


def test_migration_chain_has_exactly_one_head(script_directory):
    heads = script_directory.get_heads()
    assert len(heads) == 1, (
        '迁移链出现多个 head，容器里的 alembic upgrade head 会拒绝启动：'
        f'{heads}。请先合并分支再上线。'
    )


def test_every_declared_revision_is_reachable(script_directory):
    reachable = {revision.revision for revision in script_directory.walk_revisions()}
    declared = set(_declared_revisions())

    assert BASELINE_REVISION in reachable
    orphans = sorted(declared - reachable)
    assert not orphans, f'存在无法从 head 到达的孤立迁移: {orphans}'


def test_no_table_is_created_by_two_migrations():
    created = defaultdict(list)
    for path in sorted(VERSIONS_DIR.glob('*.py')):
        for table in _CREATE_TABLE_PATTERN.findall(path.read_text(encoding='utf-8')):
            created[table].append(path.name)

    duplicates = {table: files for table, files in created.items() if len(files) > 1}
    assert not duplicates, (
        '同一张表被多个迁移创建，串行升级时必然报 table already exists：'
        f'{duplicates}'
    )
