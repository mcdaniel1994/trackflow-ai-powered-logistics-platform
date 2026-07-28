"""Add reconciled rollup activation state.

Revision ID: 20260728_0013
Revises: 20260728_0012
Create Date: 2026-07-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260728_0013"
down_revision: str | None = "20260728_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "reporting"


def upgrade() -> None:
    op.add_column("rollup_state", sa.Column("active_pipeline_version", sa.Text()), schema=SCHEMA)
    op.add_column(
        "rollup_state",
        sa.Column("active_cutoff_at", sa.DateTime(timezone=True)),
        schema=SCHEMA,
    )
    op.add_column(
        "rollup_state",
        sa.Column("active_published_at", sa.DateTime(timezone=True)),
        schema=SCHEMA,
    )
    op.create_check_constraint(
        "ck_rollup_state_active_snapshot",
        "rollup_state",
        "("
        "active_pipeline_version IS NULL AND active_cutoff_at IS NULL "
        "AND active_published_at IS NULL"
        ") OR ("
        "active_pipeline_version IS NOT NULL AND active_cutoff_at IS NOT NULL "
        "AND active_published_at IS NOT NULL AND last_reconciled_at IS NOT NULL "
        "AND active_cutoff_at <= last_cutoff_at"
        ")",
        schema=SCHEMA,
    )


def downgrade() -> None:
    """Disposable-database rollback only; production uses forward fixes."""
    op.drop_constraint(
        "ck_rollup_state_active_snapshot",
        "rollup_state",
        schema=SCHEMA,
        type_="check",
    )
    op.drop_column("rollup_state", "active_published_at", schema=SCHEMA)
    op.drop_column("rollup_state", "active_cutoff_at", schema=SCHEMA)
    op.drop_column("rollup_state", "active_pipeline_version", schema=SCHEMA)
