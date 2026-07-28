"""Business-reporting validation, authorization, queueing, and safe failures."""

import logging
import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast
from zoneinfo import ZoneInfo

from pipelines.business_performance.queue import QueueValidationError, enqueue_manual  # type: ignore[import-untyped]
from sqlalchemy import Engine, RowMapping
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from .repository import ReportingRepository
from .schemas import (
    NextScheduledRefresh,
    PipelineRunAccepted,
    PipelineRunsResponse,
    ReportingWorkerHealth,
    WeeklyPerformanceResponse,
)
from .status import WORKER_STALE_AFTER, QueueSignals, derive_queue_state

logger = logging.getLogger(__name__)
DALLAS_TIMEZONE = ZoneInfo("America/Chicago")
DAILY_REFRESH_TIME = time(hour=7)
RESULTS_STALE_AFTER = timedelta(hours=26)


def _enabled(name: str, *, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() == "true"


@dataclass
class ReportingError(Exception):
    status_code: int
    detail: str
    error_code: str


def utc_now() -> datetime:
    return datetime.now(UTC)


class ReportingService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = ReportingRepository(session)

    @staticmethod
    def _week_start(value: str | None) -> date | None:
        if value is None:
            return None
        try:
            parsed = date.fromisoformat(value)
        except ValueError as exc:
            raise ReportingError(
                400,
                "week_start must be an ISO Monday",
                "REPORTING_INVALID_WEEK_START",
            ) from exc
        if parsed.isoweekday() != 1:
            raise ReportingError(400, "week_start must be an ISO Monday", "REPORTING_INVALID_WEEK_START")
        return parsed

    def _database_failure(self, operation: str, exc: SQLAlchemyError) -> ReportingError:
        self.session.rollback()
        logger.error("reporting_database_failure operation=%s error_type=%s", operation, type(exc).__name__)
        return ReportingError(503, "Reporting service temporarily unavailable", "REPORTING_UNAVAILABLE")

    def weekly_performance(self, requested_week_start: str | None) -> WeeklyPerformanceResponse:
        week_start = self._week_start(requested_week_start)
        try:
            if _enabled("REPORTING_ROLLUP_CUTOVER_ENABLED", default=False):
                return self._cutover_weekly_performance(week_start)
            if week_start is None:
                week_start = self.repository.default_week_start()
            if week_start is None:
                return WeeklyPerformanceResponse(week_start=None, incomplete=False, entries=[])
            return WeeklyPerformanceResponse(
                week_start=week_start,
                incomplete=self.repository.is_incomplete(week_start),
                entries=self.repository.weekly_entries(week_start),
            )
        except SQLAlchemyError as exc:
            raise self._database_failure("weekly_performance", exc) from exc

    def _cutover_weekly_performance(self, week_start: date | None) -> WeeklyPerformanceResponse:
        if not _enabled("REPORTING_COMPUTATION_ENABLED", default=True):
            raise ReportingError(
                503,
                "Reporting computation is temporarily disabled",
                "REPORTING_COMPUTATION_DISABLED",
            )
        state = self.repository.rollup_state()
        cutoff = state["active_cutoff_at"]
        published_at = state["active_published_at"]
        if cutoff is None or published_at is None or state["active_pipeline_version"] is None:
            raise ReportingError(
                503,
                "Reporting has not activated a verified snapshot",
                "REPORTING_NOT_ACTIVATED",
            )
        now = utc_now()
        worker = self.repository.worker_signals()
        worker_available = self._worker_available(worker, now=now)
        force_stale = _enabled("REPORTING_FORCE_STALE", default=False)
        if not worker_available and not force_stale:
            raise ReportingError(
                503,
                "Reporting control plane is temporarily unavailable",
                "REPORTING_CONTROL_PLANE_UNAVAILABLE",
            )
        active_week = cutoff.date() - timedelta(days=cutoff.date().weekday())
        selected_week = week_start or active_week
        entries = (
            self.repository.current_week_entries(selected_week, cutoff)
            if selected_week == active_week
            else self.repository.weekly_entries(selected_week)
        )
        is_stale = force_stale or now - cutoff > RESULTS_STALE_AFTER
        return WeeklyPerformanceResponse(
            week_start=selected_week,
            incomplete=selected_week == active_week or self.repository.is_incomplete(selected_week),
            entries=entries,
            state="stale" if is_stale else "current",
            source_cutoff_at=cutoff,
            published_at=published_at,
        )

    @staticmethod
    def _worker_available(worker: RowMapping | None, *, now: datetime) -> bool:
        return bool(
            worker is not None
            and worker["heartbeat_at"] is not None
            and now - worker["heartbeat_at"] <= WORKER_STALE_AFTER
            and worker["orchestrator_healthy"] is True
        )

    @staticmethod
    def _next_refresh(now: datetime) -> NextScheduledRefresh:
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("reporting clock must be timezone-aware")
        local_now = now.astimezone(DALLAS_TIMEZONE)
        local_occurrence = datetime.combine(local_now.date(), DAILY_REFRESH_TIME, tzinfo=DALLAS_TIMEZONE)
        if local_occurrence <= local_now:
            local_occurrence += timedelta(days=1)
        return NextScheduledRefresh(next_occurrence_utc=local_occurrence.astimezone(UTC))

    def latest_runs(self) -> PipelineRunsResponse:
        try:
            now = utc_now()
            latest = self.repository.latest_run()
            queued = self.repository.queued_runs()
            worker = self.repository.worker_signals()
            running = self.repository.running_signals()
            last_seen_at = worker["heartbeat_at"] if worker is not None else None
            last_progress_at = worker["last_progress_at"] if worker is not None else None
            orchestrator_healthy = worker["orchestrator_healthy"] if worker is not None else None
            worker_status: Literal["healthy", "stale", "unknown"]
            if last_seen_at is None:
                worker_status = "unknown"
            elif now - last_seen_at > WORKER_STALE_AFTER:
                worker_status = "stale"
            else:
                worker_status = "healthy"
            state = self.repository.rollup_state()
            cutoff = state["active_cutoff_at"]
            published_at = state["active_published_at"]
            computation_enabled = _enabled("REPORTING_COMPUTATION_ENABLED", default=True)
            force_stale = _enabled("REPORTING_FORCE_STALE", default=False)
            results_current = bool(
                computation_enabled
                and cutoff is not None
                and now - cutoff <= RESULTS_STALE_AFTER
                and worker_status == "healthy"
                and orchestrator_healthy is True
                and not force_stale
            )
            reporting_state: Literal["current", "stale", "degraded", "not_activated"]
            if cutoff is None:
                reporting_state = "not_activated"
            elif not computation_enabled or worker_status != "healthy" or orchestrator_healthy is not True:
                reporting_state = "degraded"
            elif force_stale or not results_current:
                reporting_state = "stale"
            else:
                reporting_state = "current"
            return PipelineRunsResponse(
                queue_state=derive_queue_state(
                    QueueSignals(
                        heartbeat_at=last_seen_at,
                        last_progress_at=last_progress_at,
                        orchestrator_healthy=orchestrator_healthy,
                        running_stage=running["current_stage"] if running is not None else None,
                        stage_started_at=running["stage_started_at"] if running is not None else None,
                        latest_status=latest.status if latest is not None else None,
                        latest_next_attempt_at=latest.next_attempt_at if latest is not None else None,
                        queued_count=len(queued),
                    ),
                    now=now,
                ),
                latest=latest,
                queued=queued,
                latest_successful=self.repository.latest_successful_run(),
                worker=ReportingWorkerHealth(
                    status=worker_status,
                    last_seen_at=last_seen_at,
                    last_progress_at=last_progress_at,
                    orchestrator_healthy=orchestrator_healthy,
                ),
                next_scheduled_refresh=self._next_refresh(now),
                attempts=self.repository.latest_attempts(),
                reporting_state=reporting_state,
                source_cutoff_at=cutoff,
                published_at=published_at,
                current_stage=running["current_stage"] if running is not None else None,
                stage_started_at=running["stage_started_at"] if running is not None else None,
                latest_error_code=latest.error_code if latest is not None else None,
                latest_attempt=latest.attempt if latest is not None else None,
                results_current=results_current,
            )
        except SQLAlchemyError as exc:
            raise self._database_failure("latest_runs", exc) from exc

    def request_run(
        self,
        *,
        week_start: str | None,
        force_refresh: bool,
        requested_by: str,
        role: str,
    ) -> PipelineRunAccepted:
        # Authorization lives in the service so every caller, including future
        # non-HTTP callers, receives the same server-enforced administrator gate.
        if role != "admin":
            raise ReportingError(403, "Administrator role required", "REPORTING_FORBIDDEN")
        parsed_week = self._week_start(week_start)
        try:
            if _enabled("REPORTING_ROLLUP_CUTOVER_ENABLED", default=False):
                if not _enabled("REPORTING_COMPUTATION_ENABLED", default=True):
                    raise ReportingError(
                        503,
                        "Reporting computation is temporarily disabled",
                        "REPORTING_COMPUTATION_DISABLED",
                    )
                if not self._worker_available(self.repository.worker_signals(), now=utc_now()):
                    raise ReportingError(
                        503,
                        "Reporting control plane is temporarily unavailable",
                        "REPORTING_CONTROL_PLANE_UNAVAILABLE",
                    )
            engine = cast(Engine, self.session.get_bind())
            # The API delegates insertion and coalescing to the durable DB-backed
            # queue helper; it never duplicates or executes pipeline state logic.
            run_id = enqueue_manual(
                engine,
                requested_by=requested_by,
                requested_week_start=parsed_week,
                force_refresh=force_refresh,
            )
        except QueueValidationError as exc:
            if "precedes last ledger reset" in str(exc):
                raise ReportingError(
                    400,
                    "Requested week precedes last ledger reset",
                    "REPORTING_WEEK_FROZEN",
                ) from exc
            raise ReportingError(
                400,
                "week_start must be an ISO Monday",
                "REPORTING_INVALID_WEEK_START",
            ) from exc
        except SQLAlchemyError as exc:
            raise self._database_failure("request_run", exc) from exc
        return PipelineRunAccepted(run_id=run_id)
