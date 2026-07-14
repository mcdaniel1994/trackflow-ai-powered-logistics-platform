"""Create the reporting schema, weekly facts, reset state, and durable run queue.

Revision ID: 20260714_0008
Revises: 20260714_0007
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0008"
down_revision: str | None = "20260714_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "reporting"


def upgrade() -> None:
    """Create reporting-owned persistence without granting runtime DDL privileges."""
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "weekly_warehouse_client_performance",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("warehouse", sa.Text(), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("inbound_units_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("outbound_orders_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("stockout_events_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("discrepancy_events_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("discrepancy_rate", sa.Numeric(), server_default=sa.text("0"), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "warehouse IN ('los_angeles', 'zaragoza')",
            name="ck_wwcp_warehouse",
        ),
        sa.CheckConstraint(
            "inbound_units_count >= 0 AND outbound_orders_count >= 0 "
            "AND stockout_events_count >= 0 AND discrepancy_events_count >= 0",
            name="ck_wwcp_counts",
        ),
        sa.CheckConstraint("discrepancy_rate >= 0 AND discrepancy_rate <= 1", name="ck_wwcp_rate"),
        sa.CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="ck_wwcp_week_is_monday"),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["public.clients.id"],
            name="fk_wwcp_client_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "warehouse",
            "client_id",
            "week_start",
            name="uq_wwcp_warehouse_client_week",
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_wwcp_week_start",
        "weekly_warehouse_client_performance",
        ["week_start"],
        schema=SCHEMA,
    )

    op.create_table(
        "source_ledger_state",
        sa.Column("id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("last_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_source_ledger_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.execute(
        "INSERT INTO reporting.source_ledger_state (id) VALUES (1) "
        "ON CONFLICT (id) DO NOTHING"
    )

    op.create_table(
        "incomplete_weeks",
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="ck_incomplete_weeks_monday"),
        sa.PrimaryKeyConstraint("week_start"),
        schema=SCHEMA,
    )

    op.create_table(
        "pipeline_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("pipeline_name", sa.Text(), nullable=False),
        sa.Column("pipeline_version", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.String(length=16), nullable=False),
        sa.Column("requested_by", sa.Text(), nullable=False),
        sa.Column("scheduled_business_date", sa.Date(), nullable=True),
        sa.Column("requested_week_start", sa.Date(), nullable=True),
        sa.Column("target_weeks", postgresql.ARRAY(sa.Date()), nullable=True),
        sa.Column("source_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("claim_token", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cache_nonce", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rows_extracted", sa.Integer(), nullable=True),
        sa.Column("rows_transformed", sa.Integer(), nullable=True),
        sa.Column("rows_loaded", sa.Integer(), nullable=True),
        sa.Column("source_watermark", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_summary", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "trigger_type IN ('scheduled', 'manual', 'cli')",
            name="ck_pipeline_runs_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('requested', 'running', 'retryable', 'succeeded', 'failed')",
            name="ck_pipeline_runs_status",
        ),
        sa.CheckConstraint("attempt >= 0", name="ck_pipeline_runs_attempt_nonnegative"),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code IN "
            "('EXTRACT_FAILED', 'VALIDATE_FAILED', 'LOAD_FAILED', 'DB_UNAVAILABLE', "
            "'LOCK_UNAVAILABLE', 'STALE_ABANDONED', 'MAX_ATTEMPTS_EXCEEDED')",
            name="ck_pipeline_runs_error_code",
        ),
        sa.CheckConstraint(
            "(rows_extracted IS NULL OR rows_extracted >= 0) "
            "AND (rows_transformed IS NULL OR rows_transformed >= 0) "
            "AND (rows_loaded IS NULL OR rows_loaded >= 0)",
            name="ck_pipeline_runs_row_counts_nonnegative",
        ),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_pipeline_runs_scheduled_date",
        "pipeline_runs",
        ["pipeline_name", "scheduled_business_date"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("trigger_type = 'scheduled'"),
    )
    op.create_index(
        "uq_pipeline_runs_single_active",
        "pipeline_runs",
        ["pipeline_name"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "uq_pipeline_runs_pending_manual",
        "pipeline_runs",
        ["pipeline_name", sa.text("COALESCE(requested_week_start, DATE '0001-01-01')")],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text(
            "status = 'requested' AND trigger_type = 'manual' AND cache_nonce IS NULL"
        ),
    )
    op.create_index(
        "ix_pipeline_runs_claim",
        "pipeline_runs",
        ["pipeline_name", "status", "next_attempt_at", "requested_at"],
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pipeline_runs_latest",
        "pipeline_runs",
        ["pipeline_name", sa.text("requested_at DESC")],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Drop only the additive reporting schema; public business tables remain."""
    op.drop_table("pipeline_runs", schema=SCHEMA)
    op.drop_table("incomplete_weeks", schema=SCHEMA)
    op.drop_table("source_ledger_state", schema=SCHEMA)
    op.drop_table("weekly_warehouse_client_performance", schema=SCHEMA)
    op.execute(f"DROP SCHEMA {SCHEMA}")
