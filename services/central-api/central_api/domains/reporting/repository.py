"""Read-only reporting queries; pipeline queue writes stay in the data package."""

from datetime import UTC, date, datetime, time
from typing import Any

from sqlalchemy import RowMapping, text
from sqlmodel import Session

from .schemas import (
    LatestSuccessfulRun,
    PipelineRunAttemptRead,
    PipelineRunLatest,
    QueuedPipelineRun,
    WeeklyPerformanceEntry,
)

PIPELINE_NAME = "business_performance"


class ReportingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def default_week_start(self) -> date | None:
        """Select only a week whose newest touching run is successful.

        A failed or still-running recomputation must not make older report rows
        look freshly verified, even when an earlier run for that week succeeded.
        """
        return self.session.execute(
            text(
                "SELECT max(weeks.week_start) FROM ("
                " SELECT DISTINCT week_start FROM reporting.weekly_warehouse_client_performance"
                ") AS weeks JOIN LATERAL ("
                " SELECT status FROM reporting.pipeline_runs "
                " WHERE pipeline_name = :pipeline_name AND weeks.week_start = ANY(target_weeks) "
                " ORDER BY requested_at DESC, id DESC LIMIT 1"
                ") AS latest_touching ON latest_touching.status = 'succeeded'"
            ),
            {"pipeline_name": PIPELINE_NAME},
        ).scalar_one_or_none()

    def weekly_entries(self, week_start: date) -> list[WeeklyPerformanceEntry]:
        rows = self.session.execute(
            text(
                "SELECT report.warehouse, report.client_id, client.display_name AS client_name, "
                "report.inbound_units_count, report.outbound_orders_count, "
                "report.stockout_events_count, report.discrepancy_events_count, report.discrepancy_rate "
                "FROM reporting.weekly_warehouse_client_performance AS report "
                "JOIN clients AS client ON client.id = report.client_id "
                "WHERE report.week_start = :week_start "
                "ORDER BY report.warehouse, client.display_name, report.client_id"
            ),
            {"week_start": week_start},
        ).mappings()
        return [WeeklyPerformanceEntry.model_validate(dict(row)) for row in rows]

    def current_week_entries(
        self,
        week_start: date,
        cutoff: datetime,
    ) -> list[WeeklyPerformanceEntry]:
        """Serve the incomplete active week from its verified hourly snapshot."""
        start = datetime.combine(week_start, time.min, tzinfo=UTC)
        rows = self.session.execute(
            text(
                "SELECT CASE hourly.warehouse WHEN 'LA' THEN 'los_angeles' ELSE 'zaragoza' END "
                "AS warehouse, hourly.client_id, client.display_name AS client_name, "
                "sum(hourly.inbound_units)::bigint AS inbound_units_count, "
                "sum(hourly.dispatch_order_count)::bigint AS outbound_orders_count, "
                "sum(hourly.stockout_count)::bigint AS stockout_events_count, "
                "sum(hourly.discrepancy_count)::bigint AS discrepancy_events_count, "
                "CASE WHEN sum(hourly.dispatch_order_count) = 0 THEN 0 "
                "ELSE sum(hourly.discrepancy_count)::numeric / "
                "sum(hourly.dispatch_order_count) END AS discrepancy_rate "
                "FROM reporting.hourly_activity_rollups AS hourly "
                "JOIN clients AS client ON client.id = hourly.client_id "
                "WHERE hourly.bucket_start >= :start AND hourly.bucket_start < :cutoff "
                "AND hourly.source_cutoff_at <= :cutoff "
                "GROUP BY hourly.warehouse, hourly.client_id, client.display_name "
                "ORDER BY warehouse, client.display_name, hourly.client_id"
            ),
            {"start": start, "cutoff": cutoff},
        ).mappings()
        return [WeeklyPerformanceEntry.model_validate(dict(row)) for row in rows]

    def rollup_state(self) -> RowMapping:
        return (
            self.session.execute(
                text(
                    "SELECT active_pipeline_version, active_cutoff_at, active_published_at "
                    "FROM reporting.rollup_state WHERE id = 1"
                )
            )
            .mappings()
            .one()
        )

    def is_incomplete(self, week_start: date) -> bool:
        return bool(
            self.session.execute(
                text("SELECT EXISTS (SELECT 1 FROM reporting.incomplete_weeks WHERE week_start = :week_start)"),
                {"week_start": week_start},
            ).scalar_one()
        )

    @staticmethod
    def _latest(row: RowMapping | None) -> PipelineRunLatest | None:
        return None if row is None else PipelineRunLatest.model_validate(dict(row))

    @staticmethod
    def _successful(row: RowMapping | None) -> LatestSuccessfulRun | None:
        if row is None:
            return None
        values: dict[str, Any] = dict(row)
        values["target_weeks"] = values["target_weeks"] or []
        values["rows_loaded"] = values["rows_loaded"] or 0
        return LatestSuccessfulRun.model_validate(values)

    def latest_run(self) -> PipelineRunLatest | None:
        row = (
            self.session.execute(
                text(
                    "SELECT id AS run_id, status, trigger_type, requested_by, scheduled_business_date, "
                    "requested_at, started_at, finished_at, attempt, rows_extracted, rows_transformed, "
                    "rows_loaded, error_code, next_attempt_at "
                    "FROM reporting.pipeline_runs WHERE pipeline_name = :pipeline_name "
                    "ORDER BY requested_at DESC, id DESC LIMIT 1"
                ),
                {"pipeline_name": PIPELINE_NAME},
            )
            .mappings()
            .one_or_none()
        )
        # Only the allowlisted status fields above cross the API boundary; queue
        # leases, cache nonces, object-store details, and internal summaries do not.
        return self._latest(row)

    def queued_runs(self) -> list[QueuedPipelineRun]:
        rows = self.session.execute(
            text(
                "SELECT id AS run_id, trigger_type, requested_at FROM reporting.pipeline_runs "
                "WHERE pipeline_name = :pipeline_name AND status IN ('requested', 'retryable') "
                "ORDER BY requested_at, id"
            ),
            {"pipeline_name": PIPELINE_NAME},
        ).mappings()
        return [QueuedPipelineRun.model_validate(dict(row)) for row in rows]

    def latest_successful_run(self) -> LatestSuccessfulRun | None:
        row = (
            self.session.execute(
                text(
                    "SELECT id AS run_id, finished_at, target_weeks, rows_loaded, "
                    "source_watermark AS source_cutoff_at "
                    "FROM reporting.pipeline_runs WHERE pipeline_name = :pipeline_name "
                    "AND status = 'succeeded' AND finished_at IS NOT NULL "
                    "ORDER BY finished_at DESC, requested_at DESC, id DESC LIMIT 1"
                ),
                {"pipeline_name": PIPELINE_NAME},
            )
            .mappings()
            .one_or_none()
        )
        return self._successful(row)

    def latest_attempts(self, *, limit: int = 10) -> list[PipelineRunAttemptRead]:
        """Return a bounded newest-first history without exception messages or payloads."""
        bounded_limit = min(max(limit, 1), 25)
        rows = self.session.execute(
            text(
                "SELECT attempt.run_id, attempt.stage, attempt.attempt, attempt.started_at, attempt.ended_at, "
                "attempt.duration_ms, attempt.rows_scanned, attempt.rollup_rows_written, "
                "attempt.error_code, attempt.error_type, attempt.retry_outcome, "
                "attempt.pipeline_version, attempt.build_sha "
                "FROM reporting.pipeline_run_attempts AS attempt "
                "JOIN reporting.pipeline_runs AS run ON run.id = attempt.run_id "
                "WHERE run.pipeline_name = :pipeline_name "
                "ORDER BY attempt.started_at DESC, attempt.id DESC LIMIT :limit"
            ),
            {"pipeline_name": PIPELINE_NAME, "limit": bounded_limit},
        ).mappings()
        return [PipelineRunAttemptRead.model_validate(dict(row)) for row in rows]

    def worker_signals(self) -> RowMapping | None:
        return (
            self.session.execute(
                text(
                    "SELECT heartbeat_at, last_progress_at, orchestrator_healthy "
                    "FROM reporting.worker_heartbeats "
                    "WHERE worker_name = 'reporting'"
                )
            )
            .mappings()
            .one_or_none()
        )

    def running_signals(self) -> RowMapping | None:
        return (
            self.session.execute(
                text(
                    "SELECT current_stage, stage_started_at FROM reporting.pipeline_runs "
                    "WHERE pipeline_name = :pipeline_name AND status = 'running' "
                    "ORDER BY started_at LIMIT 1"
                ),
                {"pipeline_name": PIPELINE_NAME},
            )
            .mappings()
            .one_or_none()
        )
