"""Bounded, read-only aggregate queries for telemetry reporting.

Exact metrics read the durable business tables (``stock_entries`` / ``stock_exits``);
best-effort metrics read ``telemetry_events``. All day bucketing is by UTC calendar day.
"""

from datetime import date, datetime
from typing import Any, cast

from sqlalchemy import Table, func
from sqlalchemy import select as sa_select
from sqlmodel import Session

from ..inventory.models import StockEntry, StockExit
from .models import TelemetryEvent

entry_table = cast(Table, StockEntry.__table__)  # type: ignore[attr-defined]
exit_table = cast(Table, StockExit.__table__)  # type: ignore[attr-defined]
event_table = cast(Table, TelemetryEvent.__table__)  # type: ignore[attr-defined]


def _utc_day(column: Any) -> Any:
    """Bucket a timestamptz column by its UTC calendar day."""
    return func.date(func.timezone("UTC", column))


class TelemetryRepository:
    """Keep aggregate SQL out of the service and routes."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def dispatched_by_day_warehouse(self, start: datetime, end: datetime) -> list[tuple[date, str, int]]:
        day = _utc_day(exit_table.c.created_at).label("day")
        statement = (
            sa_select(day, exit_table.c.warehouse, func.count())
            .where(
                exit_table.c.exit_type == "dispatch",
                exit_table.c.created_at >= start,
                exit_table.c.created_at < end,
            )
            .group_by(day, exit_table.c.warehouse)
        )
        return [(row[0], str(row[1]), int(row[2])) for row in self.session.execute(statement).all()]

    def received_by_day_warehouse(self, start: datetime, end: datetime) -> list[tuple[date, str, int]]:
        day = _utc_day(entry_table.c.created_at).label("day")
        statement = (
            sa_select(day, entry_table.c.warehouse, func.count())
            .where(entry_table.c.created_at >= start, entry_table.c.created_at < end)
            .group_by(day, entry_table.c.warehouse)
        )
        return [(row[0], str(row[1]), int(row[2])) for row in self.session.execute(statement).all()]

    def loss_by_day_warehouse(self, start: datetime, end: datetime) -> list[tuple[date, str, int, int]]:
        day = _utc_day(exit_table.c.created_at).label("day")
        statement = (
            sa_select(day, exit_table.c.warehouse, func.count(), func.coalesce(func.sum(exit_table.c.quantity), 0))
            .where(
                exit_table.c.exit_type == "loss",
                exit_table.c.created_at >= start,
                exit_table.c.created_at < end,
            )
            .group_by(day, exit_table.c.warehouse)
        )
        return [(row[0], str(row[1]), int(row[2]), int(row[3])) for row in self.session.execute(statement).all()]

    def event_count_by_day_warehouse(
        self, event: str, start: datetime, end: datetime
    ) -> list[tuple[date, str | None, int]]:
        day = _utc_day(event_table.c.occurred_at).label("day")
        statement = (
            sa_select(day, event_table.c.warehouse, func.count())
            .where(
                event_table.c.event == event,
                event_table.c.occurred_at >= start,
                event_table.c.occurred_at < end,
            )
            .group_by(day, event_table.c.warehouse)
        )
        return [
            (row[0], None if row[1] is None else str(row[1]), int(row[2]))
            for row in self.session.execute(statement).all()
        ]

    def event_count_by_day_reason(
        self, event: str, start: datetime, end: datetime
    ) -> list[tuple[date, str, int]]:
        day = _utc_day(event_table.c.occurred_at).label("day")
        statement = (
            sa_select(day, event_table.c.reason_code, func.count())
            .where(
                event_table.c.event == event,
                event_table.c.occurred_at >= start,
                event_table.c.occurred_at < end,
                event_table.c.reason_code.is_not(None),
            )
            .group_by(day, event_table.c.reason_code)
        )
        return [(row[0], str(row[1]), int(row[2])) for row in self.session.execute(statement).all()]

    def delete_before(self, category: str, cutoff: datetime) -> int:
        """Delete rows of a category older than the cutoff; return the row count."""
        result = self.session.execute(
            event_table.delete().where(
                event_table.c.category == category,
                event_table.c.occurred_at < cutoff,
            )
        )
        return int(cast(Any, result).rowcount or 0)
