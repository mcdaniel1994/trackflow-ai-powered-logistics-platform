"""Telemetry reporting: bounded window validation and exact/best-effort aggregation."""

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session

from . import events
from .repository import TelemetryRepository
from .schemas import (
    AccessDenialMetrics,
    AccessDenialRow,
    DispatchMetricRow,
    DispatchMetrics,
    Period,
    ReceivingMetrics,
    StockLossMetrics,
    StockLossRow,
    WarehouseCountRow,
)

logger = logging.getLogger(__name__)

MAX_RANGE_DAYS = 92


@dataclass
class TelemetryError(Exception):
    """Typed telemetry failure translated to HTTP only at the application boundary."""

    status_code: int
    detail: str


class TelemetryService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = TelemetryRepository(session)

    @staticmethod
    def _window(from_date: date, to_date: date) -> tuple[Period, datetime, datetime]:
        """Validate the requested range and return the half-open UTC datetime bounds."""
        if from_date > to_date:
            raise TelemetryError(400, "'from' must be on or before 'to'.")
        if (to_date - from_date).days > MAX_RANGE_DAYS:
            raise TelemetryError(400, f"Date range must not exceed {MAX_RANGE_DAYS} days.")
        start = datetime.combine(from_date, time.min, tzinfo=UTC)
        end = datetime.combine(to_date + timedelta(days=1), time.min, tzinfo=UTC)
        return Period(from_=from_date, to=to_date), start, end

    def _fail(self, operation: str, exc: SQLAlchemyError) -> TelemetryError:
        self.session.rollback()
        logger.error("telemetry_database_failure operation=%s error_type=%s", operation, type(exc).__name__)
        return TelemetryError(503, "Telemetry service temporarily unavailable")

    def dispatch_metrics(self, from_date: date, to_date: date) -> DispatchMetrics:
        period, start, end = self._window(from_date, to_date)
        try:
            dispatched = self.repository.dispatched_by_day_warehouse(start, end)
            rejected = self.repository.event_count_by_day_warehouse(events.DISPATCH_REJECTED, start, end)
        except SQLAlchemyError as exc:
            raise self._fail("dispatch_metrics", exc) from exc

        rejected_by_key: dict[tuple[date, str], int] = {}
        for day, warehouse, count in rejected:
            if warehouse is None:  # null warehouse is operationally useless — exclude
                continue
            rejected_by_key[(day, warehouse)] = count

        rows_by_key: dict[tuple[date, str], DispatchMetricRow] = {}
        for day, warehouse, count in dispatched:
            rows_by_key[(day, warehouse)] = DispatchMetricRow(
                date=day, warehouse=warehouse, dispatched=count, rejected=0, indicative_failure_rate=0.0
            )
        for (day, warehouse), rejected_count in rejected_by_key.items():
            existing = rows_by_key.get((day, warehouse))
            if existing is None:
                rows_by_key[(day, warehouse)] = DispatchMetricRow(
                    date=day, warehouse=warehouse, dispatched=0, rejected=rejected_count, indicative_failure_rate=0.0
                )
            else:
                existing.rejected = rejected_count

        for row in rows_by_key.values():
            total = row.dispatched + row.rejected
            row.indicative_failure_rate = round(row.rejected / total, 4) if total else 0.0

        rows = sorted(rows_by_key.values(), key=lambda r: (r.date, r.warehouse))
        return DispatchMetrics(period=period, rows=rows)

    def receiving_metrics(self, from_date: date, to_date: date) -> ReceivingMetrics:
        period, start, end = self._window(from_date, to_date)
        try:
            received = self.repository.received_by_day_warehouse(start, end)
        except SQLAlchemyError as exc:
            raise self._fail("receiving_metrics", exc) from exc
        rows = [
            WarehouseCountRow(date=day, warehouse=warehouse, count=count)
            for day, warehouse, count in sorted(received, key=lambda r: (r[0], r[1]))
        ]
        return ReceivingMetrics(period=period, rows=rows)

    def stock_loss_metrics(self, from_date: date, to_date: date) -> StockLossMetrics:
        period, start, end = self._window(from_date, to_date)
        try:
            losses = self.repository.loss_by_day_warehouse(start, end)
        except SQLAlchemyError as exc:
            raise self._fail("stock_loss_metrics", exc) from exc
        rows = [
            StockLossRow(date=day, warehouse=warehouse, count=count, units=units)
            for day, warehouse, count, units in sorted(losses, key=lambda r: (r[0], r[1]))
        ]
        return StockLossMetrics(period=period, rows=rows)

    def access_denial_metrics(self, from_date: date, to_date: date) -> AccessDenialMetrics:
        period, start, end = self._window(from_date, to_date)
        try:
            denials = self.repository.event_count_by_day_reason(events.ACCESS_DENIED, start, end)
        except SQLAlchemyError as exc:
            raise self._fail("access_denial_metrics", exc) from exc
        rows = [
            AccessDenialRow(date=day, reason=reason, count=count)
            for day, reason, count in sorted(denials, key=lambda r: (r[0], r[1]))
        ]
        return AccessDenialMetrics(period=period, rows=rows)

    def prune(self, *, operational_cutoff: datetime, security_cutoff: datetime) -> dict[str, int]:
        """Delete rows past each category's retention cutoff; commit once."""
        try:
            deleted = {
                "operational": self.repository.delete_before("operational", operational_cutoff),
                "security": self.repository.delete_before("security", security_cutoff),
            }
            self.session.commit()
        except SQLAlchemyError as exc:
            raise self._fail("prune", exc) from exc
        return deleted
