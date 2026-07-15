"""Read-only reporting queries; pipeline queue writes stay in the data package."""

from datetime import date
from typing import Any

from sqlalchemy import RowMapping, text
from sqlmodel import Session

from .schemas import (
    LatestSuccessfulRun,
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
        row = self.session.execute(
            text(
                "SELECT id AS run_id, status, trigger_type, requested_by, scheduled_business_date, "
                "requested_at, started_at, finished_at, attempt, rows_loaded, error_code "
                "FROM reporting.pipeline_runs WHERE pipeline_name = :pipeline_name "
                "ORDER BY requested_at DESC, id DESC LIMIT 1"
            ),
            {"pipeline_name": PIPELINE_NAME},
        ).mappings().one_or_none()
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
        row = self.session.execute(
            text(
                "SELECT id AS run_id, finished_at, target_weeks, rows_loaded "
                "FROM reporting.pipeline_runs WHERE pipeline_name = :pipeline_name "
                "AND status = 'succeeded' AND finished_at IS NOT NULL "
                "ORDER BY finished_at DESC, requested_at DESC, id DESC LIMIT 1"
            ),
            {"pipeline_name": PIPELINE_NAME},
        ).mappings().one_or_none()
        return self._successful(row)
