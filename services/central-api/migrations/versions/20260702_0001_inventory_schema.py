"""Create the Engagement 5 inventory schema.

Revision ID: 20260702_0001
Revises:
Create Date: 2026-07-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260702_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create SKUs first so both movement tables can enforce composite ownership."""
    op.create_table(
        "skus",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("sku", sa.String(length=80), nullable=False),
        sa.Column("client_name", sa.String(length=160), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.CheckConstraint(
            "category IN ('fashion', 'electronics', 'cosmetics')",
            name="ck_skus_category",
        ),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_skus_warehouse"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("id", "warehouse", name="uq_skus_id_warehouse"),
        sa.UniqueConstraint("sku", "warehouse", name="uq_skus_sku_warehouse"),
    )

    op.create_table(
        "stock_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("reference", sa.String(length=120), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_stock_entries_quantity_positive"),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_entries_warehouse"),
        sa.ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stock_entries_sku_warehouse",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stock_entries_created_at",
        "stock_entries",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        "ix_stock_entries_sku_warehouse_created_at",
        "stock_entries",
        ["sku_id", "warehouse", "created_at"],
        unique=False,
    )

    op.create_table(
        "stock_exits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("exit_type", sa.String(length=16), nullable=False),
        sa.Column("tracking_number", sa.String(length=120), nullable=True),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_uuid", sa.String(length=36), nullable=False),
        sa.CheckConstraint("exit_type IN ('dispatch', 'loss')", name="ck_stock_exits_exit_type"),
        sa.CheckConstraint("quantity > 0", name="ck_stock_exits_quantity_positive"),
        sa.CheckConstraint(
            "(exit_type = 'dispatch' AND tracking_number IS NOT NULL) OR "
            "(exit_type = 'loss' AND tracking_number IS NULL)",
            name="ck_stock_exits_tracking_rule",
        ),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_exits_warehouse"),
        sa.ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stock_exits_sku_warehouse",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_exits_created_at", "stock_exits", ["created_at"], unique=False)
    op.create_index(
        "ix_stock_exits_sku_warehouse_created_at",
        "stock_exits",
        ["sku_id", "warehouse", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Remove movement tables before their referenced SKU parent."""
    op.drop_index("ix_stock_exits_sku_warehouse_created_at", table_name="stock_exits")
    op.drop_index("ix_stock_exits_created_at", table_name="stock_exits")
    op.drop_table("stock_exits")
    op.drop_index("ix_stock_entries_sku_warehouse_created_at", table_name="stock_entries")
    op.drop_index("ix_stock_entries_created_at", table_name="stock_entries")
    op.drop_table("stock_entries")
    op.drop_table("skus")
