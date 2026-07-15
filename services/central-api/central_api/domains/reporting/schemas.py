"""Public contracts for weekly reports and durable pipeline status."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class WeeklyPerformanceEntry(BaseModel):
    warehouse: str
    client_id: UUID
    client_name: str
    inbound_units_count: int
    outbound_orders_count: int
    stockout_events_count: int
    discrepancy_events_count: int
    discrepancy_rate: float


class WeeklyPerformanceResponse(BaseModel):
    week_start: date | None
    incomplete: bool
    entries: list[WeeklyPerformanceEntry]


class PipelineRunLatest(BaseModel):
    run_id: UUID
    status: str
    trigger_type: str
    requested_by: str
    scheduled_business_date: date | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    attempt: int
    rows_loaded: int | None
    error_code: str | None
    next_attempt_at: datetime | None


class QueuedPipelineRun(BaseModel):
    run_id: UUID
    trigger_type: str
    requested_at: datetime


class LatestSuccessfulRun(BaseModel):
    run_id: UUID
    finished_at: datetime
    target_weeks: list[date]
    rows_loaded: int


class NextScheduledRefresh(BaseModel):
    local_time: str = "07:00"
    timezone: str = "America/Chicago"
    next_occurrence_utc: datetime


class ReportingWorkerHealth(BaseModel):
    status: Literal["healthy", "stale", "unknown"]
    last_seen_at: datetime | None
    last_progress_at: datetime | None
    orchestrator_healthy: bool | None


class PipelineRunsResponse(BaseModel):
    queue_state: Literal["idle", "processing", "queued", "retrying", "stuck", "unavailable"]
    latest: PipelineRunLatest | None
    queued: list[QueuedPipelineRun]
    latest_successful: LatestSuccessfulRun | None
    worker: ReportingWorkerHealth
    next_scheduled_refresh: NextScheduledRefresh


class PipelineRunRequest(BaseModel):
    # Keep the boundary value textual so malformed ISO dates receive the domain's
    # stable 400 error code instead of FastAPI's generic 422 response.
    week_start: str | None = None
    force_refresh: bool = False


class PipelineRunAccepted(BaseModel):
    run_id: UUID
    status: str = Field(default="requested")
