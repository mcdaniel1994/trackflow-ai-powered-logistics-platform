"""Add reporting worker heartbeat state.

Revision ID: 20260715_0009
Revises: 20260714_0008
Create Date: 2026-07-15
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0009"
down_revision: str | None = "20260714_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "worker_heartbeats",
        sa.Column("worker_name", sa.Text(), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("worker_name = 'reporting'", name="ck_worker_heartbeats_reporting_only"),
        sa.PrimaryKeyConstraint("worker_name"),
        schema="reporting",
    )


def downgrade() -> None:
    op.drop_table("worker_heartbeats", schema="reporting")
