"""Add stock ledger checkpoints so balances survive retention.

Revision ID: 20260820_0021
Revises: 20260820_0020
Create Date: 2026-08-20

Retention deletes old movements. Without a checkpoint, re-deriving a balance from
the remaining ledger yields ``(recent entries) - (recent exits)`` instead of real
stock, which makes the balance permanently unverifiable and makes any repair
attempt destructive.

The pruner writes this table immediately before each delete, recording the exact
balance the about-to-be-deleted movements produced. Derivation then bases at the
checkpoint and adds only movements at or after it, which stays correct across any
number of successive prunes.

Creating the table empty is intentional: no rows means the ledger has never been
pruned, and derivation covers its entire history exactly as before.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0021"
down_revision: str | None = "20260820_0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_ledger_checkpoints",
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("checkpoint_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "warehouse IN ('LA', 'ZGZ')", name="ck_stock_ledger_checkpoints_warehouse"
        ),
        sa.ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stock_ledger_checkpoints_sku_warehouse",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("sku_id", "warehouse"),
    )


def downgrade() -> None:
    op.drop_table("stock_ledger_checkpoints")
