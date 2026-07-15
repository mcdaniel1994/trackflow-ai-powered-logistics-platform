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
from datetime import UTC, date, datetime, timedelta

from pipelines.business_performance.flows import prefect_executor
from pipelines.business_performance.queue import DEFAULT_RECOMPUTE_WEEKS, enqueue_cli
from pipelines.business_performance.runner import RunnerStatus, run_once
from process.business_performance import iso_week_start, reset_incomplete_weeks
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


def _checkpoint_target_weeks(reset_at: datetime) -> tuple[date, ...]:
    current_week = iso_week_start(reset_at)
    return tuple(
        current_week - timedelta(weeks=offset)
        for offset in reversed(range(DEFAULT_RECOMPUTE_WEEKS))
    )


def run_reporting_checkpoint() -> bool:
    """Run one durable checkpoint request and report whether this exact request succeeded."""
    engine = get_engine()
    run_id = enqueue_cli(engine)
    result = run_once(engine, prefect_executor)
    succeeded = bool(result.status == RunnerStatus.SUCCEEDED and result.run_id == str(run_id))
    if not succeeded:
        logger.error(
            "db_size_guard_checkpoint_failed checkpoint_run_id=%s runner_status=%s claimed_run_id=%s",
            run_id,
            result.status,
            result.run_id,
        )
    return succeeded


def _reset_source_tables(
    session: Session,
    *,
    reset_at: datetime,
    target_weeks: tuple[date, ...],
    checkpoint_succeeded: bool,
) -> None:
    """Atomically clear disposable sources and persist the reporting reset boundary."""
    incomplete = reset_incomplete_weeks(
        reset_at,
        target_weeks,
        checkpoint_succeeded=checkpoint_succeeded,
    )
    session.execute(
        text(
            "TRUNCATE inventory_discrepancies, stockout_events, "
            "stock_exits, stock_entries RESTART IDENTITY"
        )
    )
    session.execute(
        text(
            "UPDATE reporting.source_ledger_state "
            "SET last_reset_at = :reset_at, updated_at = :reset_at WHERE id = 1"
        ),
        {"reset_at": reset_at},
    )
    for week_start, reason in incomplete.items():
        session.execute(
            text(
                "INSERT INTO reporting.incomplete_weeks (week_start, reason, recorded_at) "
                "VALUES (:week_start, :reason, :reset_at) "
                "ON CONFLICT (week_start) DO UPDATE SET "
                "reason = EXCLUDED.reason, recorded_at = EXCLUDED.recorded_at"
            ),
            {"week_start": week_start, "reason": reason, "reset_at": reset_at},
        )
    session.commit()


def reset_ledger(
    session: Session,
    user_uuid: str,
    settings: Settings,
    *,
    reset_at: datetime | None = None,
) -> None:
    """Checkpoint, reset, annotate, and rebuild the disposable source ledger.

    The feed is paused before the checkpoint so its published aggregates cover a stable
    source. Checkpoint failure never blocks the hard-limit reset; affected weeks are marked
    incomplete instead of being silently represented as verified history.
    """
    set_feed_enabled(session, enabled=False, note="db_size_guard: hard-limit reset in progress")
    boundary = reset_at or datetime.now(UTC)
    target_weeks = _checkpoint_target_weeks(boundary)
    try:
        checkpoint_succeeded = run_reporting_checkpoint()
    except Exception:
        # A hard-limit reset cannot wait indefinitely for reporting recovery.
        # Persist the fixed failure classification below without logging payloads.
        logger.error("db_size_guard_checkpoint_failed_before_reset")
        checkpoint_succeeded = False
    with Session(get_engine()) as work:
        _reset_source_tables(
            work,
            reset_at=boundary,
            target_weeks=target_weeks,
            checkpoint_succeeded=checkpoint_succeeded,
        )
        seed_inventory(work, user_uuid)
        backfill_history(work, user_uuid, days=settings.operations_feed_backfill_days)
    set_feed_enabled(session, enabled=True, note="db_size_guard: reset complete")
    logger.error(
        "db_size_guard_reset_complete backfill_days=%s checkpoint_succeeded=%s",
        settings.operations_feed_backfill_days,
        checkpoint_succeeded,
    )


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
