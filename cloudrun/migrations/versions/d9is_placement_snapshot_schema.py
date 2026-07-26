"""add placement snapshot persistence schema

Revision ID: d9is_placement_snapshot
Revises: 9c3cae4c1a70
Create Date: 2026-07-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d9is_placement_snapshot"
down_revision: Union[str, Sequence[str], None] = "9c3cae4c1a70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "placement_candidate",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_key", sa.String(length=80), nullable=False),
        sa.Column("stock_code", sa.String(length=20), nullable=False),
        sa.Column("bond_code", sa.String(length=20), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_key"),
    )
    op.create_index(op.f("ix_placement_candidate_candidate_key"), "placement_candidate", ["candidate_key"], unique=True)
    op.create_index(op.f("ix_placement_candidate_stock_code"), "placement_candidate", ["stock_code"], unique=False)
    op.create_index(op.f("ix_placement_candidate_bond_code"), "placement_candidate", ["bond_code"], unique=False)

    op.create_table(
        "placement_source_evidence",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False),
        sa.Column("source_identifier", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("content_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_kind", "source_identifier", name="uq_placement_source_evidence"),
    )

    op.create_table(
        "placement_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("registration_date", sa.String(length=20), nullable=True),
        sa.Column("data_as_of", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("freshness_state", sa.String(length=20), nullable=False, server_default="fresh"),
        sa.Column("stale_reason", sa.String(length=500), nullable=True),
        sa.Column("verification_state", sa.String(length=30), nullable=False, server_default="unverified"),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["placement_candidate.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id"),
    )
    op.create_index(op.f("ix_placement_snapshot_candidate_id"), "placement_snapshot", ["candidate_id"], unique=True)
    op.create_index(op.f("ix_placement_snapshot_registration_date"), "placement_snapshot", ["registration_date"], unique=False)

    op.create_table(
        "placement_observation",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("field_group", sa.String(length=30), nullable=False, server_default="snapshot"),
        sa.Column("observed_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("source_kind", sa.String(length=50), nullable=False, server_default="market"),
        sa.Column("source_priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source_evidence_id", sa.Integer(), nullable=True),
        sa.Column("payload", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("reconciliation_result", sa.String(length=30), nullable=False, server_default="accepted"),
        sa.Column("calculation_version", sa.String(length=30), nullable=True),
        sa.Column("input_snapshot_id", sa.Integer(), nullable=True),
        sa.Column("override_actor", sa.String(length=100), nullable=True),
        sa.Column("override_reason", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["placement_candidate.id"]),
        sa.ForeignKeyConstraint(["input_snapshot_id"], ["placement_snapshot.id"]),
        sa.ForeignKeyConstraint(["source_evidence_id"], ["placement_source_evidence.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_placement_observation_candidate_id"), "placement_observation", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_placement_observation_observed_at"), "placement_observation", ["observed_at"], unique=False)

    op.create_table(
        "placement_refresh_job",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scope", sa.String(length=50), nullable=False, server_default="pending"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="queued"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("requested_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.String(length=1000), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_placement_refresh_job_scope"), "placement_refresh_job", ["scope"], unique=False)
    op.create_index(op.f("ix_placement_refresh_job_status"), "placement_refresh_job", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_placement_refresh_job_status"), table_name="placement_refresh_job")
    op.drop_index(op.f("ix_placement_refresh_job_scope"), table_name="placement_refresh_job")
    op.drop_table("placement_refresh_job")
    op.drop_index(op.f("ix_placement_observation_observed_at"), table_name="placement_observation")
    op.drop_index(op.f("ix_placement_observation_candidate_id"), table_name="placement_observation")
    op.drop_table("placement_observation")
    op.drop_index(op.f("ix_placement_snapshot_registration_date"), table_name="placement_snapshot")
    op.drop_index(op.f("ix_placement_snapshot_candidate_id"), table_name="placement_snapshot")
    op.drop_table("placement_snapshot")
    op.drop_table("placement_source_evidence")
    op.drop_index(op.f("ix_placement_candidate_bond_code"), table_name="placement_candidate")
    op.drop_index(op.f("ix_placement_candidate_stock_code"), table_name="placement_candidate")
    op.drop_index(op.f("ix_placement_candidate_candidate_key"), table_name="placement_candidate")
    op.drop_table("placement_candidate")
