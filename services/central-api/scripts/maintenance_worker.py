"""Long-running maintenance scheduler for database guardrails and retention."""

from __future__ import annotations

import logging
import signal
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from datetime import time as wall_time
from threading import Event
from types import FrameType
from zoneinfo import ZoneInfo

from scripts.db_size_guard import guard_once
from scripts.prune_agent_memory import prune_once as prune_agent_memory
from scripts.prune_agent_traces import prune_once as prune_agent_traces
from scripts.prune_business_events import prune_once as prune_business_events
from scripts.prune_prefect_runs import prune_once as prune_prefect_runs
from scripts.prune_reporting_logs import prune_once as prune_reporting_logs
from scripts.prune_telemetry_events import prune_once as prune_telemetry_events

logger = logging.getLogger("central_api.maintenance_worker")

DALLAS_TIMEZONE = ZoneInfo("America/Chicago")
PRUNE_TIME = wall_time(hour=2, minute=15)
GUARD_INTERVAL_SECONDS = 15 * 60.0
SCHEDULER_TICK_SECONDS = 60.0


def _safe_failure(operation: str, exc: Exception) -> None:
    logger.error("maintenance_operation_failed operation=%s error_type=%s", operation, type(exc).__name__)


class MaintenanceSchedule:
    """Tracks process-local due times; all underlying operations are idempotent."""

    def __init__(self) -> None:
        self.next_guard_at = 0.0
        self.last_prune_date: date | None = None

    def tick(self, *, now: datetime, monotonic_now: float) -> tuple[bool, bool]:
        local = now.astimezone(DALLAS_TIMEZONE)
        guard_due = monotonic_now >= self.next_guard_at
        prune_due = local.time().replace(tzinfo=None) >= PRUNE_TIME and self.last_prune_date != local.date()
        if guard_due:
            self.next_guard_at = monotonic_now + GUARD_INTERVAL_SECONDS
        if prune_due:
            self.last_prune_date = local.date()
        return guard_due, prune_due


def run_worker(
    *,
    stop: Event,
    schedule: MaintenanceSchedule | None = None,
    tick_seconds: float = SCHEDULER_TICK_SECONDS,
) -> None:
    scheduler = schedule or MaintenanceSchedule()
    logger.info("maintenance_worker_started")
    while not stop.is_set():
        guard_due, prune_due = scheduler.tick(now=datetime.now(UTC), monotonic_now=time.monotonic())
        if guard_due:
            try:
                guard_once()
            except Exception as exc:
                _safe_failure("database_size_guard", exc)
        if prune_due:
            results: dict[str, object] = {}
            operations: tuple[tuple[str, Callable[[], object]], ...] = (
                ("telemetry_retention", prune_telemetry_events),
                ("business_event_retention", prune_business_events),
                ("agent_memory_retention", prune_agent_memory),
                ("agent_trace_retention", prune_agent_traces),
                ("reporting_log_retention", prune_reporting_logs),
            )
            for operation, runner in operations:
                try:
                    results[operation] = runner()
                except Exception as exc:
                    _safe_failure(operation, exc)
            try:
                telemetry = results.get("telemetry_retention")
                business = results.get("business_event_retention")
                reporting_logs = results.get("reporting_log_retention")
                logger.info(
                    "maintenance_prune_complete telemetry_operational=%s telemetry_security=%s "
                    "business_discrepancies=%s business_stockouts=%s memory_proposals=%s agent_traces=%s "
                    "reporting_log_files=%s reporting_log_bytes=%s",
                    telemetry.get("operational") if isinstance(telemetry, dict) else None,
                    telemetry.get("security") if isinstance(telemetry, dict) else None,
                    business.get("inventory_discrepancies") if isinstance(business, dict) else None,
                    business.get("stockout_events") if isinstance(business, dict) else None,
                    results.get("agent_memory_retention"),
                    results.get("agent_trace_retention"),
                    reporting_logs.get("files_deleted") if isinstance(reporting_logs, dict) else None,
                    reporting_logs.get("bytes_deleted") if isinstance(reporting_logs, dict) else None,
                )
            except Exception as exc:
                _safe_failure("maintenance_prune_summary", exc)
            try:
                deleted_prefect_runs = prune_prefect_runs()
                logger.info("maintenance_prefect_retention_complete flow_runs=%s", deleted_prefect_runs)
            except Exception as exc:
                # Prefect history is not business authority. API outages never block
                # TrackFlow retention or reporting work and are retried the next day.
                _safe_failure("prefect_retention", exc)
        stop.wait(tick_seconds)
    logger.info("maintenance_worker_stopped")


def _stop(stop: Event) -> Callable[[int, FrameType | None], None]:
    def handler(_signum: int, _frame: FrameType | None) -> None:
        stop.set()

    return handler


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s", force=True)
    stop = Event()
    signal.signal(signal.SIGTERM, _stop(stop))
    signal.signal(signal.SIGINT, _stop(stop))
    run_worker(stop=stop)


if __name__ == "__main__":
    main()
