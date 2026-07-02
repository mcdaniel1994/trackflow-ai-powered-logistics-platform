"""Add the centralized incident manager schema.

Revision ID: 20260702_0002
Revises: 20260702_0001
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_0002"
down_revision: str | None = "20260702_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("branch", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_uuid", sa.String(length=36), nullable=True),
        sa.Column("import_key_hash", sa.String(length=64), nullable=True),
        sa.CheckConstraint(
            "category IN ('lost_parcel', 'delivery_failure', 'inventory_discrepancy', "
            "'carrier_issue', 'returns_issue', 'warehouse_incident', 'system_failure', "
            "'client_complaint', 'other')",
            name="ck_incidents_category",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'in_progress', 'resolved', 'discarded')",
            name="ck_incidents_status",
        ),
        sa.CheckConstraint("origin IN ('customer', 'branch', 'internal')", name="ck_incidents_origin"),
        sa.CheckConstraint(
            "branch IN ('central', 'la_warehouse', 'la_office', "
            "'zaragoza_warehouse', 'zaragoza_office')",
            name="ck_incidents_branch",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("import_key_hash", name="uq_incidents_import_key_hash"),
    )
    op.create_index("ix_incidents_status", "incidents", ["status"], unique=False)
    op.create_index("ix_incidents_category", "incidents", ["category"], unique=False)
    op.create_index("ix_incidents_origin", "incidents", ["origin"], unique=False)
    op.create_index("ix_incidents_branch", "incidents", ["branch"], unique=False)
    op.create_index("ix_incidents_created_at_id", "incidents", ["created_at", "id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_incidents_created_at_id", table_name="incidents")
    op.drop_index("ix_incidents_branch", table_name="incidents")
    op.drop_index("ix_incidents_origin", table_name="incidents")
    op.drop_index("ix_incidents_category", table_name="incidents")
    op.drop_index("ix_incidents_status", table_name="incidents")
    op.drop_table("incidents")

