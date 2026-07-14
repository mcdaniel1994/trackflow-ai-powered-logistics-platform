"""Add inventory thresholds and authoritative business-event tables.

Revision ID: 20260714_0007
Revises: 20260714_0006
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260714_0007"
down_revision: str | None = "20260714_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "skus",
        sa.Column("min_stock_threshold", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_check_constraint("ck_skus_min_stock_threshold_nonnegative", "skus", "min_stock_threshold >= 0")

    op.create_table(
        "stockout_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("threshold_at_event", sa.Integer(), nullable=False),
        sa.Column("stock_after", sa.Integer(), nullable=False),
        sa.Column("stock_exit_id", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stockout_events_warehouse"),
        sa.CheckConstraint("threshold_at_event > 0", name="ck_stockout_events_threshold_positive"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stockout_events_sku_warehouse",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["stock_exit_id"], ["stock_exits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_exit_id", name="uq_stockout_events_stock_exit_id"),
    )
    op.create_index(
        "ix_stockout_events_warehouse_client_occurred_at",
        "stockout_events",
        ["warehouse", "client_id", "occurred_at"],
        unique=False,
    )

    op.create_table(
        "inventory_discrepancies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("stock_exit_id", sa.Integer(), nullable=False),
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by_user_uuid", sa.String(length=36), nullable=True),
        sa.CheckConstraint("quantity_delta <> 0", name="ck_inventory_discrepancies_quantity_delta_nonzero"),
        sa.CheckConstraint("source IN ('manual', 'feed')", name="ck_inventory_discrepancies_source"),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_inventory_discrepancies_warehouse"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_inventory_discrepancies_sku_warehouse",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["stock_exit_id"], ["stock_exits.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_exit_id", name="uq_inventory_discrepancies_stock_exit_id"),
    )
    op.create_index(
        "ix_inventory_discrepancies_warehouse_client_detected_at",
        "inventory_discrepancies",
        ["warehouse", "client_id", "detected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_inventory_discrepancies_warehouse_client_detected_at",
        table_name="inventory_discrepancies",
    )
    op.drop_table("inventory_discrepancies")
    op.drop_index("ix_stockout_events_warehouse_client_occurred_at", table_name="stockout_events")
    op.drop_table("stockout_events")
    op.drop_constraint("ck_skus_min_stock_threshold_nonnegative", "skus", type_="check")
    op.drop_column("skus", "min_stock_threshold")
