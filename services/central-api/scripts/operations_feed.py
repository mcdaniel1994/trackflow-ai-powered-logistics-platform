"""Live operations feed — synthetic-but-canonical warehouse activity generator.

This portfolio-production worker makes the Back Office feel like a live operations
platform by writing *real* inventory movements into the immutable ledger, so the
existing exact telemetry metrics (dispatch/receiving/loss) populate and move on their
own. It is NOT a demo button and has no UI: it runs as a background service.

Safety properties:
- **Single writer:** a process-lifetime PostgreSQL advisory lock. A second instance
  (rolling redeploy overlap, accidental scale-out) fails to acquire it and exits.
- **Runtime kill switch:** the ``operations_feed_control`` row is checked every tick,
  so the size guard or an operator can pause writes without a redeploy.
- **Stock never goes negative:** dispatches/losses are balance-checked against live
  stock; movements go through ``InventoryService`` (the real domain rules).
- **Honest diagnostics:** occasional deliberate over-requests are genuinely rejected
  and emit real ``inventory.dispatch.rejected`` telemetry (no fabricated data).

Usage:
    python -m scripts.operations_feed
"""

from __future__ import annotations

import logging
import random
import signal
import time
from datetime import UTC, datetime, timedelta
from types import FrameType
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Connection
from sqlmodel import Session

from central_api.core.config import Settings, get_settings
from central_api.db.session import get_engine
from central_api.domains.inventory.models import StockEntry, StockExit
from central_api.domains.inventory.repository import InventoryRepository, entry_table, exit_table, sku_table
from central_api.domains.inventory.schemas import ExitType, StockEntryCreate, StockExitCreate, Warehouse
from central_api.domains.inventory.seed import seed_inventory
from central_api.domains.inventory.service import InventoryError, InventoryService
from central_api.domains.operations.control import feed_enabled
from central_api.domains.telemetry.recorder import record_dispatch_rejection

logger = logging.getLogger("central_api.operations_feed")

# Fraction of dispatch attempts deliberately over-requested to produce honest rejections.
_OVERREQUEST_PROBABILITY = 0.08
# Relative weights for the kind of movement generated on a live tick.
_INBOUND_WEIGHT = 0.45
_LOSS_WEIGHT = 0.05  # remainder is dispatch


class FeedRunner:
    """Owns the shutdown flag so signal handlers stay tiny and testable."""

    def __init__(self) -> None:
        self.running = True

    def stop(self, _signum: int, _frame: FrameType | None) -> None:
        self.running = False


def resolve_user_uuid(settings: Settings) -> str:
    """Require a canonical service-account UUID (feed-specific, else the seed account)."""
    raw = (settings.operations_feed_user_uuid or settings.seed_user_uuid or "").strip()
    if not raw:
        raise SystemExit("OPERATIONS_FEED_USER_UUID (or SEED_USER_UUID) is required")
    try:
        return str(UUID(raw))
    except ValueError as exc:
        raise SystemExit("OPERATIONS_FEED_USER_UUID must be a valid UUID") from exc


def acquire_singleton_lock(connection: Connection, key: int) -> bool:
    """Try to take the process-lifetime advisory lock; False means another feed owns it."""
    return bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}).scalar())


def _tracking_number() -> str:
    """A plausible, PII-free carrier tracking reference for a synthetic dispatch."""
    return f"1Z{random.randint(10**11, 10**12 - 1)}"


def _list_skus(session: Session) -> list[tuple[int, str]]:
    """Return (sku_id, warehouse) pairs currently defined."""
    rows = session.execute(sa_select(sku_table.c.id, sku_table.c.warehouse)).all()
    return [(int(row[0]), str(row[1])) for row in rows]


def _recent_movement_count(session: Session, days: int) -> int:
    """Count ledger rows within the trailing window (used to skip re-backfilling)."""
    since = datetime.now(UTC) - timedelta(days=days)
    entries = int(session.scalar(sa_select(func.count()).where(entry_table.c.created_at >= since)) or 0)
    exits = int(session.scalar(sa_select(func.count()).where(exit_table.c.created_at >= since)) or 0)
    return entries + exits


def ensure_baseline(session: Session, user_uuid: str) -> None:
    """Guarantee SKUs exist so the feed has something to move (idempotent)."""
    if not _list_skus(session):
        logger.info("operations_feed_seeding_baseline")
        seed_inventory(session, user_uuid)


def backfill_history(session: Session, user_uuid: str, *, days: int) -> int:
    """Insert a rolling window of stock-safe historical movements with real past dates.

    Direct model inserts (like the seed) are used so ``created_at`` can be in the past;
    a per-(sku, warehouse) running balance keeps every dispatch/loss non-negative.
    Returns the number of rows written.
    """
    skus = _list_skus(session)
    if not skus:
        return 0
    written = 0
    now = datetime.now(UTC)
    balances: dict[tuple[int, str], int] = {}
    for sku_id, warehouse in skus:
        balances[(sku_id, warehouse)] = 0
    for day_offset in range(days, 0, -1):
        day = now - timedelta(days=day_offset)
        for sku_id, warehouse in skus:
            # A small inbound then a few outbounds, all bounded by the running balance.
            receipt = random.randint(20, 60)
            session.add(
                StockEntry(
                    sku_id=sku_id,
                    quantity=receipt,
                    reference=f"FEED-{day.date().isoformat()}-{sku_id}",
                    warehouse=warehouse,
                    created_at=day.replace(hour=random.randint(6, 10)),
                    user_uuid=user_uuid,
                )
            )
            balances[(sku_id, warehouse)] += receipt
            written += 1
            for _ in range(random.randint(1, 3)):
                available = balances[(sku_id, warehouse)]
                if available <= 0:
                    break
                qty = random.randint(1, max(1, available // 2))
                is_loss = random.random() < _LOSS_WEIGHT
                session.add(
                    StockExit(
                        sku_id=sku_id,
                        quantity=qty,
                        exit_type="loss" if is_loss else "dispatch",
                        tracking_number=None if is_loss else _tracking_number(),
                        warehouse=warehouse,
                        created_at=day.replace(hour=random.randint(11, 20)),
                        user_uuid=user_uuid,
                    )
                )
                balances[(sku_id, warehouse)] -= qty
                written += 1
    session.commit()
    logger.info("operations_feed_backfill_complete rows=%s days=%s", written, days)
    return written


def _generate_one(
    service: InventoryService, repo: InventoryRepository, sku_id: int, warehouse: str, uuid: str
) -> None:
    """Perform one balance-checked movement; honest over-requests emit real diagnostics."""
    available = repo.current_stock(sku_id, warehouse)
    roll = random.random()
    if available <= 0 or roll < _INBOUND_WEIGHT:
        service.record_inbound(
            StockEntryCreate(
                sku_id=sku_id,
                quantity=random.randint(10, 40),
                reference=f"FEED-{datetime.now(UTC).date().isoformat()}-{sku_id}",
                warehouse=Warehouse(warehouse),
            ),
            uuid,
        )
        return

    is_loss = roll > (1 - _LOSS_WEIGHT)
    over_request = (not is_loss) and random.random() < _OVERREQUEST_PROBABILITY
    quantity = available + random.randint(1, 10) if over_request else random.randint(1, max(1, available // 2))
    exit_type = ExitType.LOSS if is_loss else ExitType.DISPATCH
    payload = StockExitCreate(
        sku_id=sku_id,
        quantity=quantity,
        exit_type=exit_type,
        tracking_number=None if is_loss else _tracking_number(),
        warehouse=Warehouse(warehouse),
    )
    try:
        service.record_outbound(payload, uuid)
    except InventoryError as exc:
        # A genuinely rejected over-request: emit the same honest best-effort diagnostic
        # the HTTP boundary would, then move on. The business write did not happen.
        if exc.reject_event is not None:
            record_dispatch_rejection(
                warehouse=exc.reject_event.warehouse,
                reason_code=exc.reject_event.reason_code,
                quantity=exc.reject_event.quantity,
            )


def run_tick(session: Session, user_uuid: str, settings: Settings) -> int:
    """Generate one batch of movements. Returns the number of movement attempts made."""
    skus = _list_skus(session)
    if not skus:
        return 0
    service = InventoryService(session)
    repo = InventoryRepository(session)
    batch = random.randint(settings.operations_feed_batch_min, settings.operations_feed_batch_max)
    for _ in range(batch):
        sku_id, warehouse = random.choice(skus)
        _generate_one(service, repo, sku_id, warehouse, user_uuid)
    return batch


def _sleep_with_jitter(interval: float, runner: FeedRunner) -> None:
    """Sleep the tick interval (± up to 20% jitter), waking early on shutdown."""
    delay = interval * random.uniform(0.8, 1.2)
    deadline = time.monotonic() + delay
    while runner.running and time.monotonic() < deadline:
        time.sleep(min(0.5, deadline - time.monotonic()))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    settings = get_settings()
    if not settings.operations_feed_enabled:
        logger.info("operations_feed_disabled reason=OPERATIONS_FEED_ENABLED_false")
        return

    user_uuid = resolve_user_uuid(settings)
    engine = get_engine()
    runner = FeedRunner()
    signal.signal(signal.SIGTERM, runner.stop)
    signal.signal(signal.SIGINT, runner.stop)

    # Hold one dedicated connection for the lifetime lock; work uses separate sessions.
    lock_connection = engine.connect()
    try:
        if not acquire_singleton_lock(lock_connection, settings.operations_feed_lock_key):
            logger.warning("operations_feed_not_leader reason=advisory_lock_held_elsewhere")
            return
        logger.info("operations_feed_started interval=%.1fs", settings.operations_feed_interval_seconds)

        with Session(engine) as session:
            ensure_baseline(session, user_uuid)
            if _recent_movement_count(session, settings.operations_feed_backfill_days) == 0:
                backfill_history(session, user_uuid, days=settings.operations_feed_backfill_days)

        while runner.running:
            try:
                with Session(engine) as session:
                    if feed_enabled(session):
                        run_tick(session, user_uuid, settings)
                    else:
                        logger.info("operations_feed_paused reason=control_flag_disabled")
            except Exception:
                logger.exception("operations_feed_tick_failed")
            _sleep_with_jitter(settings.operations_feed_interval_seconds, runner)
        logger.info("operations_feed_stopped")
    finally:
        lock_connection.close()


if __name__ == "__main__":
    main()
