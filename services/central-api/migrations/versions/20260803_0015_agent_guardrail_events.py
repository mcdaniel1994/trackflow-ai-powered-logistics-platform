"""Add safe Engagement 8 guardrail intervention metadata.

Revision ID: 20260803_0015
Revises: 20260730_0014
Create Date: 2026-08-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260803_0015"
down_revision: str | None = "20260730_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_guardrail_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("layer", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("category IN ('structural', 'content', 'security')", name="ck_agent_guardrail_category"),
        sa.CheckConstraint(
            "outcome IN ('allowed', 'blocked', 'redirected', 'clarification')",
            name="ck_agent_guardrail_outcome",
        ),
        sa.CheckConstraint("duration_ms >= 0", name="ck_agent_guardrail_duration"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_guardrail_rule_created_at",
        "agent_guardrail_events",
        ["rule_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agent_guardrail_rule_created_at", table_name="agent_guardrail_events")
    op.drop_table("agent_guardrail_events")
