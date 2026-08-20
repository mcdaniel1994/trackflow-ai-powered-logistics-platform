"""Materialize per-SKU/warehouse stock balances.

Revision ID: 20260820_0020
Revises: 20260820_0019
Create Date: 2026-08-20

``current_stock`` summed the entire movement ledger for a ``(sku_id, warehouse)``
pair on every read, with no time predicate — O(ledger) per call, growing slower
forever, and the largest single consumer of production disk IO. This table holds
that value incrementally instead.

The backfill is one set-based aggregation over the current ledger, so the
materialized value is exactly what ``current_stock`` would have computed at
migration time. Every SKU gets a row, including those with no movements yet, so
the read path is a plain lookup with no outer join or COALESCE.

The table is derived, never authoritative: the ledger remains the source of
truth, and ``scripts/verify_stock_balances.py`` re-derives it to prove they agree.

There is deliberately no ``quantity >= 0`` constraint. A derived table must be
able to represent whatever the ledger says; constraining it would turn a
pre-existing data anomaly into a failed production migration. Over-dispatch is
prevented by the insufficient-stock check in ``InventoryService``.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0020"
down_revision: str | None = "20260820_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "stock_balances",
        sa.Column("sku_id", sa.Integer(), nullable=False),
        sa.Column("warehouse", sa.String(length=3), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_balances_warehouse"),
        sa.ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stock_balances_sku_warehouse",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("sku_id", "warehouse"),
    )

    # One set-based pass per source table rather than a correlated subquery per
    # SKU. Every SKU gets a row so the read path never has to handle a miss.
    op.execute(
        """
        INSERT INTO stock_balances (sku_id, warehouse, quantity, updated_at)
        SELECT
            sku.id,
            sku.warehouse,
            COALESCE(received.total, 0) - COALESCE(dispatched.total, 0),
            now()
        FROM skus AS sku
        LEFT JOIN (
            SELECT sku_id, warehouse, sum(quantity) AS total
            FROM stock_entries
            GROUP BY sku_id, warehouse
        ) AS received
            ON received.sku_id = sku.id AND received.warehouse = sku.warehouse
        LEFT JOIN (
            SELECT sku_id, warehouse, sum(quantity) AS total
            FROM stock_exits
            GROUP BY sku_id, warehouse
        ) AS dispatched
            ON dispatched.sku_id = sku.id AND dispatched.warehouse = sku.warehouse
        """
    )


def downgrade() -> None:
    op.drop_table("stock_balances")
