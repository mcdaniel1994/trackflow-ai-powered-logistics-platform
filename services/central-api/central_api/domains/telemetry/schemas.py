"""Strict, aggregates-only response contracts for telemetry reporting.

No schema exposes raw event rows; every response is a bounded aggregate.
"""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True, populate_by_name=True)


class Period(APIModel):
    """The inclusive UTC-day window echoed back on every metric response."""

    from_: date = Field(serialization_alias="from")
    to: date


class DispatchMetricRow(APIModel):
    """Exact dispatched volume plus a best-effort rejected count and diagnostic ratio."""

    date: date
    warehouse: str
    dispatched: int  # exact — from stock_exits
    rejected: int  # best-effort diagnostic — from telemetry_events
    indicative_failure_rate: float  # diagnostic only; may undercount


class WarehouseCountRow(APIModel):
    date: date
    warehouse: str
    count: int


class StockLossRow(APIModel):
    date: date
    warehouse: str
    count: int
    units: int


class AccessDenialRow(APIModel):
    date: date
    reason: str
    count: int


class DispatchMetrics(APIModel):
    period: Period
    rows: list[DispatchMetricRow]


class ReceivingMetrics(APIModel):
    period: Period
    rows: list[WarehouseCountRow]


class StockLossMetrics(APIModel):
    period: Period
    rows: list[StockLossRow]


class AccessDenialMetrics(APIModel):
    period: Period
    rows: list[AccessDenialRow]
