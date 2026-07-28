"""Preserve one sanitized durable record for every reporting attempt.

Revision ID: 20260728_0011
Revises: 20260716_0010
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260728_0011"
down_revision: str | None = "20260716_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "reporting"


def upgrade() -> None:
    op.create_table(
        "pipeline_run_attempts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("stage", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_ms", sa.BigInteger(), nullable=False),
        sa.Column("source_cutoff_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rows_scanned", sa.BigInteger(), nullable=True),
        sa.Column("rollup_rows_written", sa.BigInteger(), nullable=True),
        sa.Column("error_code", sa.Text(), nullable=True),
        sa.Column("error_type", sa.Text(), nullable=True),
        sa.Column("retry_outcome", sa.Text(), nullable=False),
        sa.Column("pipeline_version", sa.Text(), nullable=True),
        sa.Column("build_sha", sa.Text(), nullable=True),
        sa.CheckConstraint("attempt > 0", name="ck_pipeline_run_attempts_attempt_positive"),
        sa.CheckConstraint(
            "stage IS NULL OR stage IN ('extract', 'transform', 'load', 'orchestration')",
            name="ck_pipeline_run_attempts_stage",
        ),
        sa.CheckConstraint("duration_ms >= 0", name="ck_pipeline_run_attempts_duration"),
        sa.CheckConstraint(
            "(rows_scanned IS NULL OR rows_scanned >= 0) "
            "AND (rollup_rows_written IS NULL OR rollup_rows_written >= 0)",
            name="ck_pipeline_run_attempts_counts",
        ),
        sa.CheckConstraint(
            "error_code IS NULL OR error_code IN "
            "('EXTRACT_FAILED', 'VALIDATE_FAILED', 'LOAD_FAILED', 'DB_UNAVAILABLE', "
            "'LOCK_UNAVAILABLE', 'STALE_ABANDONED', 'ORCHESTRATION_FAILED', 'INTERNAL_FAILED')",
            name="ck_pipeline_run_attempts_originating_error",
        ),
        sa.CheckConstraint(
            "retry_outcome IN ('retried', 'exhausted', 'failed', 'lease_lost', 'succeeded')",
            name="ck_pipeline_run_attempts_retry_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["reporting.pipeline_runs.id"],
            name="fk_pipeline_run_attempts_run_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "attempt", name="uq_pipeline_run_attempts_run_attempt"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_pipeline_run_attempts_started_at_desc",
        "pipeline_run_attempts",
        [sa.text("started_at DESC")],
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Disposable-database rollback only; production uses forward fixes."""
    op.drop_table("pipeline_run_attempts", schema=SCHEMA)
