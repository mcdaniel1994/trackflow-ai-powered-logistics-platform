"""Bound database growth without performing an unattended destructive reset.

At the soft limit the feed is paused through its existing control row and telemetry
retention still runs. At the hard limit the same safe actions occur, but ledger reset
is refused unless an owner has deliberately paused the feed and written the exact
one-shot approval token to the control row. The token is consumed before checkpoint
work starts and cannot authorize a later reset.

Usage:
    python -m scripts.db_size_guard
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, date, datetime, timedelta

from pipelines.business_performance.queue import DEFAULT_RECOMPUTE_WEEKS, enqueue_cli
from process.business_performance import iso_week_start, reset_incomplete_weeks
from sqlalchemy import text
from sqlmodel import Session

from central_api.core.config import Settings, get_settings
from central_api.db.session import get_engine
from central_api.domains.inventory.seed import seed_inventory
from central_api.domains.operations.control import feed_enabled, set_feed_enabled
from central_api.domains.telemetry.service import TelemetryService
from scripts.operations_feed import backfill_history, resolve_user_uuid

logger = logging.getLogger("central_api.db_size_guard")

_BYTES_PER_MB = 1024 * 1024
RESET_APPROVAL_NOTE = "owner-approved-db-size-reset"
RESET_APPROVAL_CONSUMED_NOTE = "db_size_guard: owner approval consumed"
CHECKPOINT_TIMEOUT_SECONDS = 900.0
CHECKPOINT_POLL_SECONDS = 5.0


class ResetBlocked(RuntimeError):
    """The destructive path lacks a fresh, successful reporting checkpoint."""


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


def run_reporting_checkpoint(
    *,
    timeout_seconds: float = CHECKPOINT_TIMEOUT_SECONDS,
    poll_seconds: float = CHECKPOINT_POLL_SECONDS,
) -> bool:
    """Enqueue and observe one exact checkpoint; never claim or execute reporting work."""
    engine = get_engine()
    run_id = enqueue_cli(engine)
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() <= deadline:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    "SELECT status, finished_at FROM reporting.pipeline_runs "
                    "WHERE id = :run_id"
                ),
                {"run_id": run_id},
            ).mappings().one_or_none()
        if row is None:
            logger.error("db_size_guard_checkpoint_unconfirmed checkpoint_run_id=%s", run_id)
            return False
        if row["status"] == "succeeded" and row["finished_at"] is not None:
            return True
        if row["status"] == "failed":
            logger.error("db_size_guard_checkpoint_failed checkpoint_run_id=%s", run_id)
            return False
        time.sleep(poll_seconds)
    logger.error("db_size_guard_checkpoint_stale checkpoint_run_id=%s", run_id)
    return False


def consume_reset_approval(session: Session) -> bool:
    """Atomically consume the exact owner-set control note once."""
    approved = session.execute(
        text(
            "UPDATE operations_feed_control SET note = :consumed, updated_at = now() "
            "WHERE id = 1 AND enabled = false AND note = :approval RETURNING id"
        ),
        {"approval": RESET_APPROVAL_NOTE, "consumed": RESET_APPROVAL_CONSUMED_NOTE},
    ).scalar_one_or_none()
    session.commit()
    return approved is not None


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

    The caller must already have consumed an explicit owner approval. The feed stays
    paused throughout. A failed, stale, or unconfirmed checkpoint blocks all truncation.
    """
    boundary = reset_at or datetime.now(UTC)
    target_weeks = _checkpoint_target_weeks(boundary)
    try:
        checkpoint_succeeded = run_reporting_checkpoint()
    except Exception as exc:
        logger.error("db_size_guard_checkpoint_failed_before_reset error_type=%s", type(exc).__name__)
        raise ResetBlocked("reporting checkpoint could not be confirmed") from None
    if not checkpoint_succeeded:
        logger.error("db_size_guard_reset_blocked reason=checkpoint_not_successful")
        raise ResetBlocked("reporting checkpoint could not be confirmed")
    with Session(get_engine()) as work:
        _reset_source_tables(
            work,
            reset_at=boundary,
            target_weeks=target_weeks,
            checkpoint_succeeded=checkpoint_succeeded,
        )
        seed_inventory(work, user_uuid)
        backfill_history(work, user_uuid, days=settings.operations_feed_backfill_days)
    set_feed_enabled(session, enabled=True, note="db_size_guard: owner-approved reset complete")
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
            logger.error("db_size_hard_limit_reached db_size_mb=%.1f feed_paused=true", size_mb)
            prune_telemetry(session, settings)
            if feed_enabled(session):
                set_feed_enabled(
                    session,
                    enabled=False,
                    note="db_size_guard: hard limit reached; owner approval required",
                )
            if not consume_reset_approval(session):
                logger.critical(
                    "db_size_guard_reset_refused reason=owner_approval_required "
                    "approval_note=%s",
                    RESET_APPROVAL_NOTE,
                )
                return size_mb
            user_uuid = resolve_user_uuid(settings)
            try:
                reset_ledger(session, user_uuid, settings)
            except ResetBlocked:
                logger.critical("db_size_guard_reset_refused reason=checkpoint_not_successful")
        elif size_mb >= settings.db_size_soft_limit_mb:
            logger.warning(
                "db_size_soft_limit_reached db_size_mb=%.1f pruning_telemetry feed_paused=true",
                size_mb,
            )
            prune_telemetry(session, settings)
            if feed_enabled(session):
                set_feed_enabled(
                    session,
                    enabled=False,
                    note="db_size_guard: soft limit reached",
                )
    return size_mb


def entrypoint() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    guard_once()


if __name__ == "__main__":
    entrypoint()
