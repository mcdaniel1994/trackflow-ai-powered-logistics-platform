"""Add durable hourly reporting rollups and their publication cursor.

Revision ID: 20260728_0012
Revises: 20260728_0011
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0012"
down_revision: str | None = "20260728_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "reporting"


def upgrade() -> None:
    op.add_column(
        "pipeline_runs",
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        schema=SCHEMA,
    )
    op.create_index(
        "uq_pipeline_runs_scheduled_for",
        "pipeline_runs",
        ["pipeline_name", "scheduled_for"],
        unique=True,
        schema=SCHEMA,
        postgresql_where=sa.text("trigger_type = 'scheduled' AND scheduled_for IS NOT NULL"),
    )

    op.create_table(
        "hourly_activity_rollups",
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("warehouse", sa.Text(), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inbound_movement_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("inbound_units", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("dispatch_order_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("dispatch_units", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("loss_movement_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("loss_units", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("stockout_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("discrepancy_count", sa.BigInteger(), server_default=sa.text("0"), nullable=False),
        sa.Column("source_cutoff_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("pipeline_version", sa.Text(), nullable=False),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_hourly_rollups_warehouse"),
        sa.CheckConstraint(
            "date_trunc('hour', bucket_start) = bucket_start",
            name="ck_hourly_rollups_bucket_hour",
        ),
        sa.CheckConstraint(
            "inbound_movement_count >= 0 AND inbound_units >= 0 "
            "AND dispatch_order_count >= 0 AND dispatch_units >= 0 "
            "AND loss_movement_count >= 0 AND loss_units >= 0 "
            "AND stockout_count >= 0 AND discrepancy_count >= 0",
            name="ck_hourly_rollups_counts",
        ),
        sa.ForeignKeyConstraint(
            ["client_id"],
            ["public.clients.id"],
            name="fk_hourly_rollups_client_id",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("bucket_start", "warehouse", "client_id"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_hourly_rollups_week_range",
        "hourly_activity_rollups",
        ["bucket_start", "warehouse", "client_id"],
        schema=SCHEMA,
    )

    op.create_table(
        "rollup_state",
        sa.Column("id", sa.SmallInteger(), server_default=sa.text("1"), nullable=False),
        sa.Column("pipeline_version", sa.Text(), nullable=True),
        sa.Column("last_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("id = 1", name="ck_rollup_state_singleton"),
        sa.PrimaryKeyConstraint("id"),
        schema=SCHEMA,
    )
    op.execute(
        "INSERT INTO reporting.rollup_state (id) VALUES (1) "
        "ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    """Disposable-database rollback only; production uses forward fixes."""
    op.drop_table("rollup_state", schema=SCHEMA)
    op.drop_table("hourly_activity_rollups", schema=SCHEMA)
    op.drop_index("uq_pipeline_runs_scheduled_for", table_name="pipeline_runs", schema=SCHEMA)
    op.drop_column("pipeline_runs", "scheduled_for", schema=SCHEMA)
