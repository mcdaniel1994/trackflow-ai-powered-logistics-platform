"""Add the Engagement 8 agent trace store: agent_runs, agent_node_steps, agent_tool_calls.

Revision ID: 20260730_0014
Revises: 20260728_0013
Create Date: 2026-07-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260730_0014"
down_revision: str | None = "20260728_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("agent_name", sa.String(length=64), nullable=False),
        sa.Column("env", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("route_taken", sa.String(length=32), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Float(), nullable=True),
        sa.Column("guardrail_trigger_count", sa.Integer(), nullable=False),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('ok', 'error', 'rejected')", name="ck_agent_runs_status"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_runs_duration"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("trace_id", name="uq_agent_runs_trace_id"),
    )
    op.create_index("ix_agent_runs_created_at", "agent_runs", ["created_at"], unique=False)
    op.create_index(
        "ix_agent_runs_agent_status_created_at",
        "agent_runs",
        ["agent_name", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "agent_node_steps",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("parent_step_id", sa.Integer(), nullable=True),
        sa.Column("node_name", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("status IN ('ok', 'error', 'skipped')", name="ck_agent_node_steps_status"),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_node_steps_duration"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_step_id"], ["agent_node_steps.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_agent_node_steps_run_id_sequence",
        "agent_node_steps",
        ["run_id", "sequence"],
        unique=False,
    )

    op.create_table(
        "agent_tool_calls",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.Integer(), nullable=True),
        sa.Column("tool_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_type", sa.String(length=48), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("output_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('ok', 'timeout', 'error', 'denied')", name="ck_agent_tool_calls_status"
        ),
        sa.CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_tool_calls_duration"),
        sa.ForeignKeyConstraint(["run_id"], ["agent_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["step_id"], ["agent_node_steps.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_agent_tool_calls_run_id", "agent_tool_calls", ["run_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_agent_tool_calls_run_id", table_name="agent_tool_calls")
    op.drop_table("agent_tool_calls")
    op.drop_index("ix_agent_node_steps_run_id_sequence", table_name="agent_node_steps")
    op.drop_table("agent_node_steps")
    op.drop_index("ix_agent_runs_agent_status_created_at", table_name="agent_runs")
    op.drop_index("ix_agent_runs_created_at", table_name="agent_runs")
    op.drop_table("agent_runs")
