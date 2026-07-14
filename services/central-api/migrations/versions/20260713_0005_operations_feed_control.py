"""Add the operations_feed_control single-row runtime kill switch.

Revision ID: 20260713_0005
Revises: 20260709_0004
Create Date: 2026-07-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260713_0005"
down_revision: str | None = "20260709_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "operations_feed_control",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_operations_feed_control_singleton"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Seed the singleton row enabled so a fresh deploy is ready to run the feed.
    op.execute(
        "INSERT INTO operations_feed_control (id, enabled, note, updated_at) "
        "VALUES (1, true, 'seeded by migration', now()) ON CONFLICT (id) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("operations_feed_control")
