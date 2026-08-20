"""Bounded 30-day retention for the movement ledger and the events referencing it.

This is the job that makes the deployment self-limiting: without it the ledger
grows forever and `db_size_guard` eventually pauses the live feed at its soft
limit. See `docs/design/movement-ledger-retention.md` for the `spec.md` §8.4
design this implements.

Three properties matter more than speed here.

**Foreign-key order.** `inventory_discrepancies` and `stockout_events` hold
`ON DELETE RESTRICT` foreign keys into `stock_exits`. Children must go first or
the parent DELETE raises. Critically, children are selected *by their parent's
age*, not their own timestamp: a discrepancy can be detected days after the
dispatch it describes, so a child inside the retention window may point at a
parent outside it. Filtering children on their own timestamp would leave exactly
those rows behind and fail the parent delete.

**Micro-batching.** Every delete is `WHERE id IN (SELECT id ... LIMIT n)` with a
commit and a short sleep between batches, so autovacuum can reclaim dead tuples
continuously instead of facing one large transaction. A single unbounded DELETE
here would hold a long transaction and spike IOwait on a Nano instance.

**A floor under the reporting window.** Reporting recomputes a trailing
`DEFAULT_RECOMPUTE_WEEKS` (3 weeks / 21 days). Deleting inside that window would
make those weeks recompute against a partial ledger and republish *lower*
numbers with no error. The job refuses to run below the floor rather than
silently corrupting the weekly report.

Note that deleting rows does not return space to the operating system: the freed
pages are at the front of the heap, so plain VACUUM cannot truncate them. What
this buys is a *plateau* -- the ledger stops growing because new rows reuse freed
pages -- which is what keeps the database below the guard's soft limit forever.
Reclaiming the space itself needs a one-off VACUUM FULL or pg_repack.

Usage:
    python -m scripts.prune_movement_ledger
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, cast

from sqlalchemy import text
from sqlalchemy.engine import CursorResult
from sqlmodel import Session

from central_api.core.config import Settings, get_settings
from central_api.db.session import get_engine
from central_api.domains.inventory.balances import (
    verify_stock_balances,
    write_ledger_checkpoint,
)

logger = logging.getLogger("central_api.prune_movement_ledger")

DEFAULT_BATCH_SIZE = 1_000
DEFAULT_SLEEP_SECONDS = 0.5
# Bound one night's work so a large backlog is spread across runs instead of
# holding the maintenance worker for hours. The job is idempotent and resumes.
DEFAULT_MAX_SECONDS = 1_800.0

# Reporting recomputes a trailing 3 weeks (DEFAULT_RECOMPUTE_WEEKS). Retention
# must clear that with margin, or recomputed weeks silently lose movements.
REPORTING_RECOMPUTE_DAYS = 21
MINIMUM_MOVEMENT_RETENTION_DAYS = 25


class RetentionWindowTooShort(RuntimeError):
    """Configured retention would delete inside the reporting recompute window."""


class BalancesDrifted(RuntimeError):
    """Stored balances disagree with the ledger, so deletion is not safe."""


@dataclass(frozen=True)
class _Step:
    """One FK-ordered delete, expressed as the id set it is allowed to remove."""

    name: str
    statement: str


# Children are keyed off the parent's created_at so no child can outlive the
# stock_exit it references. Parents follow once nothing points at them.
_STEPS: tuple[_Step, ...] = (
    _Step(
        "inventory_discrepancies",
        "DELETE FROM inventory_discrepancies WHERE stock_exit_id IN ("
        "  SELECT exit.id FROM stock_exits AS exit"
        "  WHERE exit.created_at < :cutoff"
        "  AND EXISTS ("
        "    SELECT 1 FROM inventory_discrepancies AS child"
        "    WHERE child.stock_exit_id = exit.id"
        "  )"
        "  ORDER BY exit.id LIMIT :batch)",
    ),
    _Step(
        "stockout_events",
        "DELETE FROM stockout_events WHERE stock_exit_id IN ("
        "  SELECT exit.id FROM stock_exits AS exit"
        "  WHERE exit.created_at < :cutoff"
        "  AND EXISTS ("
        "    SELECT 1 FROM stockout_events AS child"
        "    WHERE child.stock_exit_id = exit.id"
        "  )"
        "  ORDER BY exit.id LIMIT :batch)",
    ),
    _Step(
        "stock_exits",
        "DELETE FROM stock_exits WHERE id IN ("
        "  SELECT id FROM stock_exits WHERE created_at < :cutoff"
        "  ORDER BY id LIMIT :batch)",
    ),
    _Step(
        "stock_entries",
        "DELETE FROM stock_entries WHERE id IN ("
        "  SELECT id FROM stock_entries WHERE created_at < :cutoff"
        "  ORDER BY id LIMIT :batch)",
    ),
)


def retention_cutoff(now: datetime, retention_days: int) -> datetime:
    """Return the exclusive cutoff, refusing a window inside the recompute range."""
    if retention_days < MINIMUM_MOVEMENT_RETENTION_DAYS:
        raise RetentionWindowTooShort(
            "movement retention must exceed the reporting recompute window"
        )
    return now - timedelta(days=retention_days)


def _delete_in_batches(
    session: Session,
    step: _Step,
    *,
    cutoff: datetime,
    batch_size: int,
    sleep_seconds: float,
    deadline: float,
    monotonic: Callable[[], float],
    sleep: Callable[[float], None],
) -> tuple[int, bool]:
    """Delete one step in micro-batches. Returns (rows deleted, finished)."""
    deleted = 0
    while True:
        if monotonic() >= deadline:
            return deleted, False
        result = cast(
            CursorResult[Any],
            session.execute(text(step.statement), {"cutoff": cutoff, "batch": batch_size}),
        )
        removed = int(result.rowcount or 0)
        # Each batch is its own transaction so autovacuum can reclaim as we go.
        session.commit()
        deleted += removed
        if removed == 0:
            return deleted, True
        sleep(sleep_seconds)


def prune_once(
    *,
    now: datetime | None = None,
    settings: Settings | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    max_seconds: float = DEFAULT_MAX_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, int]:
    """Enforce the retention window in FK order. Safe to interrupt and rerun."""
    resolved = settings or get_settings()
    cutoff = retention_cutoff(now or datetime.now(UTC), resolved.movement_retention_days)
    deadline = monotonic() + max_seconds
    deleted: dict[str, int] = {}
    with Session(get_engine()) as session:
        # Deletion is irreversible and destroys the evidence needed to diagnose a
        # drifting balance, so refuse while any disagreement exists. The
        # maintenance worker reconciles on every guard tick, so a healthy system
        # never reaches this; if it does, something is wrong with the incremental
        # path and pruning would bury it.
        drifted = verify_stock_balances(session)
        if drifted:
            logger.error(
                "movement_ledger_prune_refused reason=balances_drifted drift_rows=%s",
                len(drifted),
            )
            raise BalancesDrifted("stock balances disagree with the ledger")

        # Checkpoint first and commit: the rows about to be deleted fall strictly
        # below the cutoff, so an interrupted prune still leaves every balance
        # derivable. Doing this after deletion would lose them permanently.
        checkpointed = write_ledger_checkpoint(session, cutoff)
        session.commit()
        logger.info(
            "movement_ledger_checkpoint_written rows=%s cutoff=%s",
            checkpointed,
            cutoff.isoformat(),
        )

        for step in _STEPS:
            removed, finished = _delete_in_batches(
                session,
                step,
                cutoff=cutoff,
                batch_size=batch_size,
                sleep_seconds=sleep_seconds,
                deadline=deadline,
                monotonic=monotonic,
                sleep=sleep,
            )
            deleted[step.name] = removed
            if not finished:
                # Stop at the boundary rather than deleting parents whose children
                # were not fully removed; the next run resumes from here.
                logger.warning(
                    "movement_ledger_prune_incomplete stopped_at=%s reason=time_budget",
                    step.name,
                )
                break
    return deleted


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    deleted = prune_once()
    logger.info(
        "movement_ledger_prune_complete discrepancies=%s stockouts=%s exits=%s entries=%s",
        deleted.get("inventory_discrepancies", 0),
        deleted.get("stockout_events", 0),
        deleted.get("stock_exits", 0),
        deleted.get("stock_entries", 0),
    )


if __name__ == "__main__":
    main()
