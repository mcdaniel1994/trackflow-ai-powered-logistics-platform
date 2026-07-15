"""Business-reporting validation, authorization, queueing, and safe failures."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, cast
from zoneinfo import ZoneInfo

from pipelines.business_performance.queue import QueueValidationError, enqueue_manual  # type: ignore[import-untyped]
from sqlalchemy import Engine
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

logger = logging.getLogger(__name__)
DALLAS_TIMEZONE = ZoneInfo("America/Chicago")
DAILY_REFRESH_TIME = time(hour=7)
WORKER_STALE_AFTER = timedelta(seconds=30)


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
            last_seen_at = self.repository.worker_last_seen_at()
            worker_status: Literal["healthy", "stale", "unknown"]
            if last_seen_at is None:
                worker_status = "unknown"
            elif now - last_seen_at > WORKER_STALE_AFTER:
                worker_status = "stale"
            else:
                worker_status = "healthy"
            return PipelineRunsResponse(
                latest=self.repository.latest_run(),
                queued=self.repository.queued_runs(),
                latest_successful=self.repository.latest_successful_run(),
                worker=ReportingWorkerHealth(status=worker_status, last_seen_at=last_seen_at),
                next_scheduled_refresh=self._next_refresh(now),
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
