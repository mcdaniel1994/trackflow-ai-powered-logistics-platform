"""Create stable clients and replace mutable SKU client names with UUID ownership.

Revision ID: 20260714_0006
Revises: 20260713_0005
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0006"
down_revision: str | None = "20260713_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Backfill every legacy name before making UUID ownership mandatory."""
    op.create_table(
        "clients",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_name", name="uq_clients_display_name"),
    )
    op.execute(
        sa.text(
            "INSERT INTO clients (display_name) "
            "SELECT DISTINCT client_name FROM skus ORDER BY client_name"
        )
    )
    op.add_column("skus", sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.execute(
        sa.text(
            "UPDATE skus SET client_id = clients.id FROM clients "
            "WHERE clients.display_name = skus.client_name"
        )
    )
    # This assertion turns any unexpected legacy null into a migration failure,
    # keeping the column drop data-preserving and transactionally reversible.
    op.alter_column("skus", "client_id", nullable=False)
    op.create_foreign_key("skus_client_id_fkey", "skus", "clients", ["client_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_skus_client_id", "skus", ["client_id"], unique=False)
    op.drop_column("skus", "client_name")


def downgrade() -> None:
    """Restore display names before removing UUID linkage and the client table."""
    op.add_column("skus", sa.Column("client_name", sa.String(length=160), nullable=True))
    op.execute(
        sa.text(
            "UPDATE skus SET client_name = clients.display_name FROM clients "
            "WHERE clients.id = skus.client_id"
        )
    )
    op.alter_column("skus", "client_name", nullable=False)
    op.drop_index("ix_skus_client_id", table_name="skus")
    op.drop_constraint("skus_client_id_fkey", "skus", type_="foreignkey")
    op.drop_column("skus", "client_id")
    op.drop_table("clients")
