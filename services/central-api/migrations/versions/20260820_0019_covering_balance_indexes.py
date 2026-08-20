"""Replace the movement composite indexes with covering balance indexes.

Revision ID: 20260820_0019
Revises: 20260818_0018
Create Date: 2026-08-20

``InventoryRepository.current_stock`` sums ``quantity`` for one ``(sku_id,
warehouse)`` pair with no time predicate. The previous
``(sku_id, warehouse, created_at)`` indexes carried a trailing column that query
never filters on, and did not carry ``quantity``, so every matching row required a
heap visit. Production ``pg_stat_statements`` recorded 1,980,064 executions against
1,982,049 scans of those indexes -- they served that query and effectively nothing
else; every reporting rollup filters ``created_at`` alone and is served by
``ix_stock_entries_created_at`` / ``ix_stock_exits_created_at``.

Replacing the trailing key column with ``INCLUDE (quantity)`` makes the balance
query index-only, removing the heap reads that were exhausting the instance's disk
IO budget. Index count is unchanged, so write amplification does not increase.

Both statements run ``CONCURRENTLY`` outside a transaction: the live operations feed
writes to these tables continuously and must not be blocked by a full index build.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260820_0019"
down_revision: str | None = "20260818_0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NEW_INDEXES = (
    ("ix_stock_entries_sku_warehouse_quantity", "stock_entries"),
    ("ix_stock_exits_sku_warehouse_quantity", "stock_exits"),
)
_OLD_INDEXES = (
    ("ix_stock_entries_sku_warehouse_created_at", "stock_entries", "created_at"),
    ("ix_stock_exits_sku_warehouse_created_at", "stock_exits", "created_at"),
)


def upgrade() -> None:
    """Build the covering indexes first, then drop the superseded ones."""
    with op.get_context().autocommit_block():
        for index_name, table in _NEW_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                f"ON public.{table} (sku_id, warehouse) INCLUDE (quantity)"
            )
        for index_name, _table, _trailing in _OLD_INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS public.{index_name}")


def downgrade() -> None:
    """Restore the original composite indexes before removing the covering ones."""
    with op.get_context().autocommit_block():
        for index_name, table, trailing in _OLD_INDEXES:
            op.execute(
                f"CREATE INDEX CONCURRENTLY IF NOT EXISTS {index_name} "
                f"ON public.{table} (sku_id, warehouse, {trailing})"
            )
        for index_name, _table in _NEW_INDEXES:
            op.execute(f"DROP INDEX CONCURRENTLY IF EXISTS public.{index_name}")
