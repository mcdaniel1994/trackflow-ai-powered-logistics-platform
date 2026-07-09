"""Add the telemetry_events best-effort diagnostics table.

Revision ID: 20260709_0004
Revises: 20260702_0003
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260709_0004"
down_revision: str | None = "20260702_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "telemetry_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("service", sa.String(length=32), nullable=False),
        sa.Column("env", sa.String(length=16), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=True),
        sa.Column("reason_code", sa.String(length=48), nullable=True),
        sa.Column("value", sa.Integer(), nullable=True),
        sa.Column("properties", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("category IN ('operational', 'security')", name="ck_telemetry_events_category"),
        sa.CheckConstraint(
            "warehouse IS NULL OR warehouse IN ('LA', 'ZGZ')",
            name="ck_telemetry_events_warehouse",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_telemetry_events_event_occurred_at",
        "telemetry_events",
        ["event", "occurred_at"],
        unique=False,
    )
    op.create_index(
        "ix_telemetry_events_event_warehouse_occurred_at",
        "telemetry_events",
        ["event", "warehouse", "occurred_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_telemetry_events_event_warehouse_occurred_at", table_name="telemetry_events")
    op.drop_index("ix_telemetry_events_event_occurred_at", table_name="telemetry_events")
    op.drop_table("telemetry_events")
