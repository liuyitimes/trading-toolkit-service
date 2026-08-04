"""新增 LOF 溢价观测、交易日历和任务进度

Revision ID: e1a2_lof_premium
Revises: d9is_placement_snapshot
Create Date: 2026-08-04
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e1a2_lof_premium'
down_revision: Union[str, Sequence[str], None] = 'd9is_placement_snapshot'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'trading_calendar',
        sa.Column('trading_date', sa.Date(), nullable=False),
        sa.Column('market', sa.String(length=20), nullable=False, server_default='cn-a'),
        sa.Column('source', sa.String(length=100), nullable=False),
        sa.Column('source_version', sa.String(length=100), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('trading_date'),
    )
    op.create_table(
        'lof_premium_observation',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_code', sa.String(length=20), nullable=False),
        sa.Column('trading_date', sa.Date(), nullable=False),
        sa.Column('close_price', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('unit_nav', sa.Numeric(precision=18, scale=6), nullable=False),
        sa.Column('premium_rate', sa.Numeric(precision=12, scale=6), nullable=False),
        sa.Column('price_source', sa.String(length=100), nullable=False),
        sa.Column('price_source_url', sa.String(length=1000), nullable=True),
        sa.Column('nav_source', sa.String(length=100), nullable=False),
        sa.Column('nav_source_url', sa.String(length=1000), nullable=True),
        sa.Column('nav_date', sa.Date(), nullable=False),
        sa.Column('captured_by', sa.String(length=20), nullable=False, server_default='capture'),
        sa.Column('source_version', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('observed_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_code', 'trading_date', name='uq_lof_premium_observation_fund_date'),
    )
    op.create_index(op.f('ix_lof_premium_observation_fund_code'), 'lof_premium_observation', ['fund_code'], unique=False)
    op.create_index(op.f('ix_lof_premium_observation_trading_date'), 'lof_premium_observation', ['trading_date'], unique=False)
    op.create_table(
        'lof_premium_job',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_key', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='queued'),
        sa.Column('cursor', sa.String(length=100), nullable=True),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_key'),
    )
    op.create_index(op.f('ix_lof_premium_job_status'), 'lof_premium_job', ['status'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lof_premium_job_status'), table_name='lof_premium_job')
    op.drop_table('lof_premium_job')
    op.drop_index(op.f('ix_lof_premium_observation_trading_date'), table_name='lof_premium_observation')
    op.drop_index(op.f('ix_lof_premium_observation_fund_code'), table_name='lof_premium_observation')
    op.drop_table('lof_premium_observation')
    op.drop_table('trading_calendar')
