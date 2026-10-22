"""新增 LOF 溢价观测、交易日历和任务进度（已合并为空修订）

Revision ID: e1a2_lof_premium
Revises: d9is_placement_snapshot
Create Date: 2026-08-04

历史说明：本修订与 `lof_premium_observations` 各自从 `d9is_placement_snapshot`
派生，创建了**同名但不同列定义**的三张表（trading_calendar、
lof_premium_observation、lof_premium_job）。两者同时存在于迁移链中会导致：

1. `alembic upgrade head` 报 "Multiple head revisions are present"；
2. 即使强行升级，第二条分支建同名表也会直接失败。

以 `cloudrun/models/lof_premium.py` 为准判定：模型用的是
`nav_published_date` / `write_source` / `version` / `job_type` / `attempt_count`
这一组列，即 `lof_premium_observations` 的定稿版本。本修订的行定义（`nav_date`、
`captured_by`、`source_version`、`job_key`）与模型不符，属于被取代的草稿。

因此这里保留修订号（兼容已经打过 `e1a2_lof_premium` 标记的数据库，避免
"Can't locate revision" 报错），但实际不再执行任何 DDL，由
`m1022_merge_lof_heads` 把两条分支收口成单一 head。
"""

from typing import Sequence, Union


revision: str = 'e1a2_lof_premium'
down_revision: Union[str, Sequence[str], None] = 'd9is_placement_snapshot'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """空修订：表结构由 lof_premium_observations 负责创建。"""


def downgrade() -> None:
    """空修订：无需撤销任何结构变更。"""
