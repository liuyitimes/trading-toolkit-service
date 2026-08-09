"""add LOF execution rules registry

Revision ID: lof_execution_rules_registry
Revises: lof_premium_observations
Create Date: 2026-08-09
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'lof_execution_rules_registry'
down_revision: Union[str, Sequence[str], None] = 'lof_premium_observations'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lof_execution_fund',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_code', sa.String(length=20), nullable=False),
        sa.Column('fund_name', sa.String(length=200), nullable=True),
        sa.Column('exchange', sa.String(length=10), nullable=False),
        sa.Column('share_class', sa.String(length=80), nullable=False, server_default='listed'),
        sa.Column('discovery_status', sa.String(length=30), nullable=False, server_default='unavailable'),
        sa.Column('discovery_reason', sa.String(length=500), nullable=True),
        sa.Column('subscription_status', sa.String(length=20), nullable=True),
        sa.Column('redemption_status', sa.String(length=20), nullable=True),
        sa.Column('status_checked_at', sa.DateTime(), nullable=True),
        sa.Column('status_source_url', sa.String(length=1000), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_code'),
    )
    op.create_index(op.f('ix_lof_execution_fund_fund_code'), 'lof_execution_fund', ['fund_code'], unique=True)
    op.create_index(op.f('ix_lof_execution_fund_exchange'), 'lof_execution_fund', ['exchange'], unique=False)
    op.create_table(
        'lof_execution_evidence',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('source_kind', sa.String(length=50), nullable=False),
        sa.Column('source_identifier', sa.String(length=200), nullable=False),
        sa.Column('source_title', sa.String(length=500), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=False),
        sa.Column('applies_to', sa.String(length=80), nullable=False),
        sa.Column('published_at', sa.Date(), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('verified_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('content_hash', sa.String(length=128), nullable=True),
        sa.Column('excerpt', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_kind', 'source_identifier', name='uq_lof_execution_evidence'),
    )
    op.create_table(
        'lof_execution_rule',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fund_id', sa.Integer(), nullable=True),
        sa.Column('exchange', sa.String(length=10), nullable=False),
        sa.Column('share_class', sa.String(length=80), nullable=False, server_default='listed'),
        sa.Column('field_key', sa.String(length=80), nullable=False),
        sa.Column('value_text', sa.String(length=200), nullable=True),
        sa.Column('numeric_value', sa.Float(), nullable=True),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='verified'),
        sa.Column('reason', sa.String(length=500), nullable=True),
        sa.Column('source_priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('evidence_id', sa.Integer(), nullable=True),
        sa.Column('effective_from', sa.Date(), nullable=True),
        sa.Column('effective_to', sa.Date(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['evidence_id'], ['lof_execution_evidence.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['lof_execution_fund.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_id', 'exchange', 'share_class', 'field_key', 'evidence_id', name='uq_lof_execution_rule_version'),
    )
    op.create_index(op.f('ix_lof_execution_rule_exchange'), 'lof_execution_rule', ['exchange'], unique=False)
    op.create_index(op.f('ix_lof_execution_rule_field_key'), 'lof_execution_rule', ['field_key'], unique=False)
    op.create_index(op.f('ix_lof_execution_rule_fund_id'), 'lof_execution_rule', ['fund_id'], unique=False)
    op.create_table(
        'lof_execution_job',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_type', sa.String(length=40), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('cursor', sa.Text(), nullable=True),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failure_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_type'),
    )
    op.create_index(op.f('ix_lof_execution_job_job_type'), 'lof_execution_job', ['job_type'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_lof_execution_job_job_type'), table_name='lof_execution_job')
    op.drop_table('lof_execution_job')
    op.drop_index(op.f('ix_lof_execution_rule_fund_id'), table_name='lof_execution_rule')
    op.drop_index(op.f('ix_lof_execution_rule_field_key'), table_name='lof_execution_rule')
    op.drop_index(op.f('ix_lof_execution_rule_exchange'), table_name='lof_execution_rule')
    op.drop_table('lof_execution_rule')
    op.drop_table('lof_execution_evidence')
    op.drop_index(op.f('ix_lof_execution_fund_exchange'), table_name='lof_execution_fund')
    op.drop_index(op.f('ix_lof_execution_fund_fund_code'), table_name='lof_execution_fund')
    op.drop_table('lof_execution_fund')
