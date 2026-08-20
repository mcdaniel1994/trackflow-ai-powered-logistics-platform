"""Add DEV-55 asynchronous task dead-letter evidence.

Revision ID: 20260820_0019
Revises: 20260818_0018
Create Date: 2026-08-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0019"
down_revision: str | None = "20260818_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "async_task_failures",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("error_code", sa.String(length=64), nullable=False),
        sa.Column("error_message", sa.String(length=200), nullable=False),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt > 0", name="ck_async_task_failures_attempt_positive"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("task_id", name="uq_async_task_failures_task_id"),
    )
    op.create_index("ix_async_task_failures_failed_at", "async_task_failures", ["failed_at"])
    op.drop_constraint("ck_rfp_tickets_status", "rfp_tickets", type_="check")
    op.create_check_constraint(
        "ck_rfp_tickets_status",
        "rfp_tickets",
        "status IN ('analyzing', 'waiting_for_approval', 'drafting', "
        "'under_evaluation', 'done', 'discarded', 'failed')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_rfp_tickets_status", "rfp_tickets", type_="check")
    op.create_check_constraint(
        "ck_rfp_tickets_status",
        "rfp_tickets",
        "status IN ('analyzing', 'waiting_for_approval', 'drafting', 'under_evaluation', 'done', 'discarded')",
    )
    op.drop_index("ix_async_task_failures_failed_at", table_name="async_task_failures")
    op.drop_table("async_task_failures")
