"""merge LOF 溢价持久化与场内规则注册表两条分支

Revision ID: m1022_merge_lof_heads
Revises: e1a2_lof_premium, lof_execution_rules_registry

背景：两个功能分支各自从 `d9is_placement_snapshot` 派生了迁移，合并后出现两个
head。容器启动固定执行 `alembic upgrade head`，多 head 会让它直接报
"Multiple head revisions are present" 而拒绝启动，发布随之失败。

本修订不含任何 DDL，仅把两条分支收口成单一 head：
- 已执行过 `lof_execution_rules_registry` 的库会补跑 `e1a2_lof_premium`
- 已执行过 `e1a2_lof_premium` 的库会补跑 `lof_execution_rules_registry`
- 空库会依次执行全部迁移

两条分支都是纯新增建表，彼此无字段依赖，合并不改变业务语义。
"""

from typing import Sequence, Union

revision: str = 'm1022_merge_lof_heads'
down_revision: Union[str, Sequence[str], None] = (
    'e1a2_lof_premium',
    'lof_execution_rules_registry',
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """仅收口分支，无结构变更。"""


def downgrade() -> None:
    """回退到合并前状态时无需撤销任何结构变更。"""
