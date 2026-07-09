"""SQLModel persistence for best-effort telemetry diagnostics.

This table stores ONLY best-effort diagnostic events (rejected dispatches and API
access-denials). Exact metrics (dispatch/receiving volume, stock loss) are computed
directly from the durable ``stock_entries`` / ``stock_exits`` business tables and are
never duplicated here.
"""

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel

# Bounded vocabularies enforced at the database boundary.
CATEGORY_VALUES: tuple[str, ...] = ("operational", "security")
WAREHOUSE_VALUES: tuple[str, ...] = ("LA", "ZGZ")


def utc_now() -> datetime:
    return datetime.now(UTC)


class TelemetryEvent(SQLModel, table=True):
    """One best-effort diagnostic event with PII-free, allowlisted fields."""

    __tablename__ = "telemetry_events"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("category IN ('operational', 'security')", name="ck_telemetry_events_category"),
        CheckConstraint(
            "warehouse IS NULL OR warehouse IN ('LA', 'ZGZ')",
            name="ck_telemetry_events_warehouse",
        ),
        Index("ix_telemetry_events_event_occurred_at", "event", "occurred_at"),
        Index("ix_telemetry_events_event_warehouse_occurred_at", "event", "warehouse", "occurred_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    event: str = Field(sa_column=Column(String(64), nullable=False))
    category: str = Field(sa_column=Column(String(16), nullable=False))
    occurred_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    service: str = Field(sa_column=Column(String(32), nullable=False))
    env: str = Field(sa_column=Column(String(16), nullable=False))
    severity: str = Field(sa_column=Column(String(16), nullable=False))
    warehouse: str | None = Field(default=None, sa_column=Column(String(3), nullable=True))
    reason_code: str | None = Field(default=None, sa_column=Column(String(48), nullable=True))
    value: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    properties: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
