"""Derivation, verification, and repair of the materialized stock balances.

`stock_balances` is maintained incrementally by `InventoryService`, one movement
at a time, inside the transaction that writes the movement and under the SKU lock
that already serialises it. That is the production path and it cannot drift under
concurrency.

Three things happen outside that path, and this module exists for them:

**Bulk writes.** Seeding, feed backfill, and the size guard's reset write many
movements at once without the per-movement path, so they re-derive instead of
threading a delta through every loop.

**Deploy rollover.** A deployment migrates the database, then swaps containers.
Until the swap completes the *old* image keeps writing movements without knowing
`stock_balances` exists, so every deploy leaves drift behind. `reconcile` closes
that window: the maintenance worker runs it at startup and on every guard tick,
so drift is corrected automatically instead of silently authorising dispatches
the ledger cannot cover.

**Retention.** Once old movements are deleted, re-deriving from the whole ledger
is no longer correct -- it would yield `(recent entries) - (recent exits)` rather
than real stock. Every derivation here is therefore based at the ledger
checkpoint the pruner writes *before* each delete, which keeps the balance
verifiable and repairable indefinitely. Writing the checkpoint before deleting
is also what makes an interrupted prune safe: the deleted rows sit strictly
below the watermark, so they never contributed to the sum.

If the checkpoints are inconsistent, these helpers refuse rather than compute
from an ambiguous base. A wrong balance is worse than a failed job, because it
silently authorises dispatches against stock that does not exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlmodel import Session

# Predates any possible movement, so an unpruned ledger derives over its entirety.
BEGINNING_OF_TIME = datetime(1970, 1, 1, tzinfo=UTC)


class LedgerCheckpointError(RuntimeError):
    """The checkpoint state cannot support a correct derivation."""


@dataclass(frozen=True)
class BalanceDrift:
    """One SKU/warehouse whose stored balance disagrees with the derived value."""

    sku_id: int
    warehouse: str
    stored: int
    derived: int

    @property
    def delta(self) -> int:
        """Correction needed: positive means the stored balance is too low."""
        return self.derived - self.stored


# Movements at or after the checkpoint, added to the checkpointed base. With no
# checkpoint the base is 0 and the watermark admits the whole ledger, which is
# exactly the pre-retention behaviour.
_DERIVE_BALANCES = """
    SELECT
        sku.id AS sku_id,
        sku.warehouse AS warehouse,
        COALESCE(checkpoint.quantity, 0)
            + COALESCE(received.total, 0)
            - COALESCE(dispatched.total, 0) AS quantity
    FROM skus AS sku
    LEFT JOIN stock_ledger_checkpoints AS checkpoint
        ON checkpoint.sku_id = sku.id AND checkpoint.warehouse = sku.warehouse
    LEFT JOIN (
        SELECT sku_id, warehouse, sum(quantity) AS total
        FROM stock_entries
        WHERE created_at >= :watermark
        GROUP BY sku_id, warehouse
    ) AS received
        ON received.sku_id = sku.id AND received.warehouse = sku.warehouse
    LEFT JOIN (
        SELECT sku_id, warehouse, sum(quantity) AS total
        FROM stock_exits
        WHERE created_at >= :watermark
        GROUP BY sku_id, warehouse
    ) AS dispatched
        ON dispatched.sku_id = sku.id AND dispatched.warehouse = sku.warehouse
"""


def checkpoint_watermark(session: Session) -> datetime | None:
    """Return the single checkpoint instant, or None when the ledger is intact.

    Raises when rows disagree. A split checkpoint has no single correct base, and
    guessing one produces a plausible but wrong balance.
    """
    row = session.execute(
        text(
            "SELECT min(checkpoint_at) AS low, max(checkpoint_at) AS high, "
            "count(*) AS row_count FROM stock_ledger_checkpoints"
        )
    ).one()
    if int(row.row_count) == 0:
        return None
    if row.low != row.high:
        raise LedgerCheckpointError("stock ledger checkpoints disagree on their instant")
    return cast(datetime, row.high)


def _watermark_params(session: Session) -> dict[str, Any]:
    return {"watermark": checkpoint_watermark(session) or BEGINNING_OF_TIME}


def write_ledger_checkpoint(session: Session, cutoff: datetime) -> int:
    """Record every balance as of `cutoff`, so movements before it may be deleted.

    Must be committed before any deletion. Derivation is relative to the previous
    checkpoint, so successive prunes chain exactly rather than each needing the
    full ledger.
    """
    params = _watermark_params(session)
    if cutoff <= params["watermark"]:
        raise LedgerCheckpointError("checkpoint cutoff must advance beyond the current watermark")
    result = cast(
        CursorResult[Any],
        session.execute(
            text(
                """
                INSERT INTO stock_ledger_checkpoints (sku_id, warehouse, quantity, checkpoint_at)
                SELECT
                    sku.id,
                    sku.warehouse,
                    COALESCE(checkpoint.quantity, 0)
                        + COALESCE(received.total, 0)
                        - COALESCE(dispatched.total, 0),
                    :cutoff
                FROM skus AS sku
                LEFT JOIN stock_ledger_checkpoints AS checkpoint
                    ON checkpoint.sku_id = sku.id AND checkpoint.warehouse = sku.warehouse
                LEFT JOIN (
                    SELECT sku_id, warehouse, sum(quantity) AS total
                    FROM stock_entries
                    WHERE created_at >= :watermark AND created_at < :cutoff
                    GROUP BY sku_id, warehouse
                ) AS received
                    ON received.sku_id = sku.id AND received.warehouse = sku.warehouse
                LEFT JOIN (
                    SELECT sku_id, warehouse, sum(quantity) AS total
                    FROM stock_exits
                    WHERE created_at >= :watermark AND created_at < :cutoff
                    GROUP BY sku_id, warehouse
                ) AS dispatched
                    ON dispatched.sku_id = sku.id AND dispatched.warehouse = sku.warehouse
                ON CONFLICT (sku_id, warehouse) DO UPDATE
                    SET quantity = EXCLUDED.quantity, checkpoint_at = EXCLUDED.checkpoint_at
                """
            ),
            {"cutoff": cutoff, **params},
        ),
    )
    return int(result.rowcount or 0)


def rebuild_stock_balances(session: Session) -> int:
    """Re-derive every balance from the checkpoint plus later movements.

    Caller owns the transaction. Rows are upserted rather than deleted and
    reinserted, so the foreign key stays satisfied and no concurrent reader
    observes a missing row. Raises `LedgerCheckpointError` rather than writing a
    balance it cannot derive correctly.
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
            ),
            _watermark_params(session),
        ),
    )
    return int(result.rowcount or 0)


def verify_stock_balances(session: Session) -> list[BalanceDrift]:
    """Return every row where the stored balance disagrees with the derived value.

    Read-only, and honest after retention: it compares against the checkpointed
    base plus retained movements, not against a truncated ledger.
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
        ),
        _watermark_params(session),
    ).all()
    return [
        BalanceDrift(sku_id=int(r[0]), warehouse=str(r[1]), stored=int(r[2]), derived=int(r[3]))
        for r in rows
    ]


def reconcile_stock_balances(session: Session) -> list[BalanceDrift]:
    """Correct any drift and return what was corrected. Caller commits.

    Deliberately self-healing rather than fail-closed: the common cause is a
    deploy rollover, which is routine and leaves a balance that over-states
    stock. The corrected rows are returned so the caller can log them loudly --
    silent repair would hide a genuine bug in the incremental path.
    """
    drifted = verify_stock_balances(session)
    if drifted:
        rebuild_stock_balances(session)
    return drifted
