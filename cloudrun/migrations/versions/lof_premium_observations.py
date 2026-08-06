"""add LOF premium observation persistence schema

Revision ID: lof_premium_observations
Revises: d9is_placement_snapshot
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "lof_premium_observations"
down_revision: Union[str, Sequence[str], None] = "d9is_placement_snapshot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trading_calendar",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("calendar_date", sa.Date(), nullable=False),
        sa.Column("is_trading_day", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("source_version", sa.String(length=100), nullable=False),
        sa.Column("imported_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("calendar_date", name="uq_trading_calendar_date"),
    )
    op.create_index(op.f("ix_trading_calendar_calendar_date"), "trading_calendar", ["calendar_date"], unique=True)

    op.create_table(
        "lof_premium_observation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fund_code", sa.String(length=20), nullable=False),
        sa.Column("trading_date", sa.Date(), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("unit_nav", sa.Float(), nullable=False),
        sa.Column("premium_rate", sa.Float(), nullable=False),
        sa.Column("price_source", sa.String(length=50), nullable=False),
        sa.Column("price_source_url", sa.String(length=500), nullable=True),
        sa.Column("nav_source", sa.String(length=50), nullable=False),
        sa.Column("nav_source_url", sa.String(length=500), nullable=True),
        sa.Column("nav_published_date", sa.Date(), nullable=True),
        sa.Column("write_source", sa.String(length=30), nullable=False, server_default="scheduled_capture"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fund_code", "trading_date", name="uq_lof_premium_observation"),
    )
    op.create_index(op.f("ix_lof_premium_observation_fund_code"), "lof_premium_observation", ["fund_code"], unique=False)
    op.create_index(op.f("ix_lof_premium_observation_trading_date"), "lof_premium_observation", ["trading_date"], unique=False)

    op.create_table(
        "lof_premium_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_type", sa.String(length=30), nullable=False),
        sa.Column("scope_year", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("cursor", sa.Text(), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_type", "scope_year", name="uq_lof_premium_job"),
    )


def downgrade() -> None:
    op.drop_table("lof_premium_job")
    op.drop_index(op.f("ix_lof_premium_observation_trading_date"), table_name="lof_premium_observation")
    op.drop_index(op.f("ix_lof_premium_observation_fund_code"), table_name="lof_premium_observation")
    op.drop_table("lof_premium_observation")
    op.drop_index(op.f("ix_trading_calendar_calendar_date"), table_name="trading_calendar")
    op.drop_table("trading_calendar")
