"""Set-based rebuild of the materialized stock balances.

The incremental path in ``InventoryService`` maintains ``stock_balances`` one
movement at a time, under the SKU lock, and is what production uses. Bulk paths
-- seeding, feed backfill, and the size guard's ledger reset -- insert many
movements at once outside that lock, so they re-derive the whole table instead of
threading a delta through every loop. Re-deriving is the same aggregation the
migration used, so both paths agree by construction.

This is also the drift check: ``verify_stock_balances`` reports any row where the
materialized value disagrees with the ledger, without changing anything.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlmodel import Session

# Every SKU gets a row, including those with no movements, so reads never miss.
_DERIVE_BALANCES = """
    SELECT
        sku.id AS sku_id,
        sku.warehouse AS warehouse,
        COALESCE(received.total, 0) - COALESCE(dispatched.total, 0) AS quantity
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


@dataclass(frozen=True)
class BalanceDrift:
    """One SKU/warehouse whose stored balance disagrees with the ledger."""

    sku_id: int
    warehouse: str
    stored: int
    derived: int


def rebuild_stock_balances(session: Session) -> int:
    """Re-derive every balance from the ledger. Caller owns the transaction.

    Used after bulk movement writes. Rows are upserted rather than deleted and
    reinserted so the foreign key from ``stock_balances`` stays satisfied and no
    concurrent reader observes a missing row.
    """
    result = cast(
        CursorResult[Any],
        session.execute(
            text(
                f"""
            INSERT INTO stock_balances (sku_id, warehouse, quantity, updated_at)
            SELECT derived.sku_id, derived.warehouse, derived.quantity, now()
            FROM ({_DERIVE_BALANCES}) AS derived
            ON CONFLICT (sku_id, warehouse) DO UPDATE
                SET quantity = EXCLUDED.quantity, updated_at = EXCLUDED.updated_at
                """
            )
        ),
    )
    return int(result.rowcount or 0)


def verify_stock_balances(session: Session) -> list[BalanceDrift]:
    """Return every row where the materialized balance disagrees with the ledger.

    Read-only. An empty list is the proof that materializing stock preserved
    computed-stock correctness.
    """
    rows = session.execute(
        text(
            f"""
            SELECT
                derived.sku_id,
                derived.warehouse,
                COALESCE(balance.quantity, 0) AS stored,
                derived.quantity AS derived_quantity
            FROM ({_DERIVE_BALANCES}) AS derived
            LEFT JOIN stock_balances AS balance
                ON balance.sku_id = derived.sku_id
                AND balance.warehouse = derived.warehouse
            WHERE COALESCE(balance.quantity, 0) <> derived.quantity
            ORDER BY derived.sku_id, derived.warehouse
            """
        )
    ).all()
    return [
        BalanceDrift(sku_id=int(r[0]), warehouse=str(r[1]), stored=int(r[2]), derived=int(r[3]))
        for r in rows
    ]
