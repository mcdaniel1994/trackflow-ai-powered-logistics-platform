"""Pure, deterministic weekly KPI transformations with reset-aware windows."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from .vocabulary import WAREHOUSE_VOCABULARY

INBOUND: Final = "inbound_order_created"
OUTBOUND: Final = "outbound_order_created"
STOCKOUT: Final = "stock_threshold_triggered"
DISCREPANCY: Final = "inventory_discrepancy_detected"
EVENT_SOURCES: Final[tuple[str, ...]] = (INBOUND, OUTBOUND, STOCKOUT, DISCREPANCY)

EventRecord = Mapping[str, object]
Activity = Mapping[str, Sequence[EventRecord]]
DimensionInput = tuple[str, str | UUID]


class TransformError(ValueError):
    """Raised when source data cannot produce a trustworthy complete result."""


@dataclass(frozen=True, order=True)
class WeeklyPerformanceRow:
    warehouse: str
    client_id: str
    week_start: date
    inbound_units_count: int
    outbound_orders_count: int
    stockout_events_count: int
    discrepancy_events_count: int
    discrepancy_rate: Decimal

    def business_values(self) -> dict[str, object]:
        """Expose deterministic values without load-owned timestamps or identifiers."""
        return asdict(self)


@dataclass(frozen=True)
class _NormalizedEvent:
    source: str
    event_id: int
    occurred_at: datetime
    quantity_or_delta: int | None
    warehouse: str
    client_id: str


def _aware_utc(value: object, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise TransformError(f"{field} must be a timezone-aware datetime")
    return value.astimezone(UTC)


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise TransformError(f"{field} must be a positive integer")
    return value


def _nonzero_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value == 0:
        raise TransformError(f"{field} must be a non-zero integer")
    return value


def _client_id(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise TransformError("client_id must be a UUID") from exc


def _warehouse(value: object) -> str:
    if not isinstance(value, str) or value not in WAREHOUSE_VOCABULARY:
        raise TransformError("warehouse must be one of: LA, ZGZ")
    return WAREHOUSE_VOCABULARY[value]


def _quantity_for_source(source: str, record: EventRecord) -> int | None:
    if source in {INBOUND, OUTBOUND}:
        return _positive_int(record.get("quantity"), "quantity")
    if source == DISCREPANCY:
        return _nonzero_int(record.get("quantity_delta"), "quantity_delta")
    return None


def _normalize_source(source: str, records: Sequence[EventRecord]) -> tuple[_NormalizedEvent, ...]:
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise TransformError(f"{source} must be a sequence of records")

    deduplicated: dict[int, _NormalizedEvent] = {}
    for record in records:
        if not isinstance(record, Mapping):
            raise TransformError(f"{source} records must be mappings")
        event_id = _positive_int(record.get("id"), "id")
        normalized = _NormalizedEvent(
            source=source,
            event_id=event_id,
            occurred_at=_aware_utc(record.get("occurred_at"), "occurred_at"),
            quantity_or_delta=_quantity_for_source(source, record),
            warehouse=_warehouse(record.get("warehouse")),
            client_id=_client_id(record.get("client_id")),
        )
        prior = deduplicated.get(event_id)
        if prior is not None and prior != normalized:
            raise TransformError(f"conflicting duplicate {source} id={event_id}")
        deduplicated[event_id] = normalized
    return tuple(sorted(deduplicated.values(), key=lambda event: event.event_id))


def _normalize_activity(activity: Activity) -> dict[str, tuple[_NormalizedEvent, ...]]:
    if set(activity) != set(EVENT_SOURCES):
        raise TransformError("activity must contain exactly the four business event sources")
    # Validate the entire input before returning any transformed rows; callers
    # therefore never observe a partial report after a bad source record.
    return {source: _normalize_source(source, activity[source]) for source in EVENT_SOURCES}


def iso_week_start(timestamp: datetime) -> date:
    """Return the Monday for the ISO week containing one absolute UTC instant."""
    utc_timestamp = _aware_utc(timestamp, "timestamp")
    return date.fromisocalendar(utc_timestamp.isocalendar().year, utc_timestamp.isocalendar().week, 1)


def compute_inbound_volume(records: Sequence[EventRecord]) -> int:
    return sum(event.quantity_or_delta or 0 for event in _normalize_source(INBOUND, records))


def compute_outbound_throughput(records: Sequence[EventRecord]) -> int:
    return len(_normalize_source(OUTBOUND, records))


def compute_stockout_frequency(records: Sequence[EventRecord]) -> int:
    return len(_normalize_source(STOCKOUT, records))


def compute_discrepancy_rate(discrepancy_count: int, outbound_orders_count: int) -> Decimal:
    for value, field in (
        (discrepancy_count, "discrepancy_count"),
        (outbound_orders_count, "outbound_orders_count"),
    ):
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TransformError(f"{field} must be a non-negative integer")
    if discrepancy_count > outbound_orders_count:
        raise TransformError("discrepancy events cannot exceed outbound orders")
    if outbound_orders_count == 0:
        return Decimal(0)
    return Decimal(discrepancy_count) / Decimal(outbound_orders_count)


def _target_week(value: object) -> date:
    if isinstance(value, datetime) or not isinstance(value, date):
        raise TransformError("target weeks must be date values")
    if value.isoweekday() != 1:
        raise TransformError("target weeks must start on Monday")
    return value


def recomputable_weeks(target_weeks: Iterable[date], last_reset_at: datetime | None) -> tuple[date, ...]:
    """Return weeks whose complete Monday-to-Monday span is after the reset boundary."""
    weeks = tuple(sorted({_target_week(week) for week in target_weeks}))
    if last_reset_at is None:
        return weeks
    boundary = _aware_utc(last_reset_at, "last_reset_at")
    return tuple(
        week
        for week in weeks
        if datetime.combine(week, time.min, tzinfo=UTC) >= boundary
    )


def validate_requested_week(requested_week: date, last_reset_at: datetime | None) -> date:
    week = _target_week(requested_week)
    if last_reset_at is not None and week not in recomputable_weeks((week,), last_reset_at):
        raise TransformError("week precedes last ledger reset")
    return week


def reset_incomplete_weeks(
    reset_at: datetime,
    target_weeks: Iterable[date],
    *,
    checkpoint_succeeded: bool,
) -> dict[date, str]:
    """Pure reset-marking decision reused later by the guarded reset workflow."""
    reset_week = iso_week_start(reset_at)
    weeks = tuple(sorted({_target_week(week) for week in target_weeks}))
    if not checkpoint_succeeded:
        return {week: "reset_checkpoint_failed" for week in weeks}
    return {reset_week: "ledger_reset"}


def week_is_incomplete(week_start: date, incomplete_weeks: Mapping[date, str] | Iterable[date]) -> bool:
    week = _target_week(week_start)
    return week in incomplete_weeks


def _dimension_pairs(pairs: Iterable[DimensionInput]) -> tuple[tuple[str, str], ...]:
    normalized: set[tuple[str, str]] = set()
    for pair in pairs:
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise TransformError("SKU dimensions must be (warehouse, client_id) pairs")
        normalized.add((_warehouse(pair[0]), _client_id(pair[1])))
    return tuple(sorted(normalized))


def assemble_weekly_rows(
    activity: Activity,
    *,
    sku_pairs: Iterable[DimensionInput],
    target_weeks: Iterable[date],
    last_reset_at: datetime | None = None,
) -> list[WeeklyPerformanceRow]:
    """Build a dense, deterministic grid for every SKU-bearing dimension and valid week."""
    normalized = _normalize_activity(activity)
    pairs = _dimension_pairs(sku_pairs)
    weeks = recomputable_weeks(target_weeks, last_reset_at)
    valid_pairs = set(pairs)
    valid_weeks = set(weeks)
    counters: dict[tuple[date, str, str], dict[str, int]] = {
        (week, warehouse, client_id): {source: 0 for source in EVENT_SOURCES}
        for week in weeks
        for warehouse, client_id in pairs
    }

    for source, events in normalized.items():
        for event in events:
            pair = (event.warehouse, event.client_id)
            if pair not in valid_pairs:
                raise TransformError("activity references a warehouse/client pair without a SKU")
            week = iso_week_start(event.occurred_at)
            if week not in valid_weeks:
                continue
            key = (week, event.warehouse, event.client_id)
            counters[key][source] += cast(int, event.quantity_or_delta) if source == INBOUND else 1

    rows: list[WeeklyPerformanceRow] = []
    for (week, warehouse, client_id), values in sorted(counters.items()):
        outbound_count = values[OUTBOUND]
        discrepancy_count = values[DISCREPANCY]
        rows.append(
            WeeklyPerformanceRow(
                warehouse=warehouse,
                client_id=client_id,
                week_start=week,
                inbound_units_count=values[INBOUND],
                outbound_orders_count=outbound_count,
                stockout_events_count=values[STOCKOUT],
                discrepancy_events_count=discrepancy_count,
                discrepancy_rate=compute_discrepancy_rate(discrepancy_count, outbound_count),
            )
        )
    return rows


def source_content_digest(activity: Activity) -> str:
    """Hash canonical source content so count-preserving changes still miss cache."""
    normalized = _normalize_activity(activity)
    canonical = [
        {
            "source": source,
            "records": [
                (
                    event.event_id,
                    event.occurred_at.isoformat().replace("+00:00", "Z"),
                    event.quantity_or_delta,
                    event.warehouse,
                    event.client_id,
                )
                for event in events
            ],
        }
        for source, events in normalized.items()
    ]
    payload = json.dumps(canonical, separators=(",", ":"), ensure_ascii=True).encode()
    return hashlib.sha256(payload).hexdigest()
