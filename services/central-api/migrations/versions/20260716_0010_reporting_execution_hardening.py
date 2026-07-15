"""Add Prefect correlation and truthful reporting progress signals.

Revision ID: 20260716_0010
Revises: 20260715_0009
Create Date: 2026-07-16
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260716_0010"
down_revision: str | None = "20260715_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _error_constraint() -> sa.CheckConstraint:
    return sa.CheckConstraint(
        "error_code IS NULL OR error_code IN "
        "('EXTRACT_FAILED', 'VALIDATE_FAILED', 'LOAD_FAILED', 'DB_UNAVAILABLE', "
        "'LOCK_UNAVAILABLE', 'STALE_ABANDONED', 'MAX_ATTEMPTS_EXCEEDED', "
        "'ORCHESTRATION_FAILED', 'INTERNAL_FAILED')",
        name="ck_pipeline_runs_error_code",
    )


def upgrade() -> None:
    op.add_column(
        "worker_heartbeats",
        sa.Column("last_progress_at", sa.DateTime(timezone=True), nullable=True),
        schema="reporting",
    )
    op.add_column(
        "worker_heartbeats",
        sa.Column("orchestrator_healthy", sa.Boolean(), nullable=True),
        schema="reporting",
    )
    op.add_column(
        "pipeline_runs",
        sa.Column("prefect_flow_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        schema="reporting",
    )
    op.add_column("pipeline_runs", sa.Column("current_stage", sa.Text(), nullable=True), schema="reporting")
    op.add_column(
        "pipeline_runs",
        sa.Column("stage_started_at", sa.DateTime(timezone=True), nullable=True),
        schema="reporting",
    )
    op.create_check_constraint(
        "ck_pipeline_runs_current_stage",
        "pipeline_runs",
        "current_stage IS NULL OR current_stage IN ('extract', 'transform', 'load')",
        schema="reporting",
    )
    op.drop_constraint("ck_pipeline_runs_error_code", "pipeline_runs", schema="reporting", type_="check")
    op.create_check_constraint(
        _error_constraint().name,
        "pipeline_runs",
        str(_error_constraint().sqltext),
        schema="reporting",
    )


def downgrade() -> None:
    op.drop_constraint("ck_pipeline_runs_error_code", "pipeline_runs", schema="reporting", type_="check")
    op.create_check_constraint(
        "ck_pipeline_runs_error_code",
        "pipeline_runs",
        "error_code IS NULL OR error_code IN "
        "('EXTRACT_FAILED', 'VALIDATE_FAILED', 'LOAD_FAILED', 'DB_UNAVAILABLE', "
        "'LOCK_UNAVAILABLE', 'STALE_ABANDONED', 'MAX_ATTEMPTS_EXCEEDED')",
        schema="reporting",
    )
    op.drop_constraint("ck_pipeline_runs_current_stage", "pipeline_runs", schema="reporting", type_="check")
    op.drop_column("pipeline_runs", "stage_started_at", schema="reporting")
    op.drop_column("pipeline_runs", "current_stage", schema="reporting")
    op.drop_column("pipeline_runs", "prefect_flow_run_id", schema="reporting")
    op.drop_column("worker_heartbeats", "orchestrator_healthy", schema="reporting")
    op.drop_column("worker_heartbeats", "last_progress_at", schema="reporting")
