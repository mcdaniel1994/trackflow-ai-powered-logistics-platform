"""Bound Supabase Free-tier storage for the live operations feed.

The 5-second feed writes real ledger rows continuously, so the database must be kept
well clear of Supabase Free's 500 MB cap. This job (a Coolify scheduled task, ~every
15 minutes) measures the database and takes graduated, automatic action:

- below the soft limit: log the size only.
- at/above the soft limit (default 400 MB): prune telemetry immediately and log a warning.
- at/above the hard limit (default 450 MB): pause the feed (kill-switch row), run a
  ledger-safe reset/reseed, then re-enable — keeping the DB bounded without ever leaving
  the stock ledger in an inconsistent state.

The business ledger is deliberately disposable in this portfolio environment (documented
in docs/runbooks/telemetry-inventory.md); the reset truncates synthetic movements and
rebuilds a consistent baseline + rolling window rather than partially deleting rows (which
would corrupt computed stock).

Usage:
    python -m scripts.db_size_guard
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlmodel import Session

from central_api.core.config import Settings, get_settings
from central_api.db.session import get_engine
from central_api.domains.inventory.seed import seed_inventory
from central_api.domains.operations.control import set_feed_enabled
from central_api.domains.telemetry.service import TelemetryService
from scripts.operations_feed import backfill_history, resolve_user_uuid

logger = logging.getLogger("central_api.db_size_guard")

_BYTES_PER_MB = 1024 * 1024


def database_size_mb(session: Session) -> float:
    """Return the current database size in megabytes."""
    size_bytes = int(session.scalar(text("SELECT pg_database_size(current_database())")) or 0)
    return size_bytes / _BYTES_PER_MB


def prune_telemetry(session: Session, settings: Settings) -> dict[str, int]:
    """Prune telemetry rows past each category's retention window (same rule as the daily job)."""
    now = datetime.now(UTC)
    return TelemetryService(session).prune(
        operational_cutoff=now - timedelta(days=settings.telemetry_operational_retention_days),
        security_cutoff=now - timedelta(days=settings.telemetry_security_retention_days),
    )


def reset_ledger(session: Session, user_uuid: str, settings: Settings) -> None:
    """Ledger-safe reset: pause the feed, truncate movements, reseed a consistent window.

    Truncating and reseeding (rather than deleting arbitrary old rows) keeps computed
    stock (received minus dispatched/lost) internally consistent by construction. The feed
    is paused first and re-enabled last so no concurrent write lands mid-reset.
    """
    set_feed_enabled(session, enabled=False, note="db_size_guard: hard-limit reset in progress")
    with Session(get_engine()) as work:
        # Phase 2 business events reference outbound rows with RESTRICT FKs, so
        # disposable resets clear dependents and ledger rows as one atomic set.
        work.execute(
            text(
                "TRUNCATE inventory_discrepancies, stockout_events, "
                "stock_exits, stock_entries RESTART IDENTITY"
            )
        )
        work.commit()
        seed_inventory(work, user_uuid)
        backfill_history(work, user_uuid, days=settings.operations_feed_backfill_days)
    set_feed_enabled(session, enabled=True, note="db_size_guard: reset complete")
    logger.error("db_size_guard_reset_complete backfill_days=%s", settings.operations_feed_backfill_days)


def guard_once() -> float:
    """Measure the database and take graduated action. Returns the pre-action size (MB)."""
    settings = get_settings()
    engine = get_engine()
    with Session(engine) as session:
        size_mb = database_size_mb(session)
        logger.info(
            "db_size_measured db_size_mb=%.1f soft=%s hard=%s",
            size_mb,
            settings.db_size_soft_limit_mb,
            settings.db_size_hard_limit_mb,
        )

        if size_mb >= settings.db_size_hard_limit_mb:
            logger.error("db_size_hard_limit_reached db_size_mb=%.1f", size_mb)
            user_uuid = resolve_user_uuid(settings)
            reset_ledger(session, user_uuid, settings)
        elif size_mb >= settings.db_size_soft_limit_mb:
            logger.warning("db_size_soft_limit_reached db_size_mb=%.1f pruning_telemetry", size_mb)
            prune_telemetry(session, settings)
    return size_mb


def entrypoint() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    guard_once()


if __name__ == "__main__":
    entrypoint()
