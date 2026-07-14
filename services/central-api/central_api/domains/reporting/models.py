"""SQLModel metadata for reports, reset boundaries, and the durable run queue."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel

REPORTING_SCHEMA = "reporting"
SOURCE_LEDGER_STATE_ID = 1


def utc_now() -> datetime:
    return datetime.now(UTC)


class WeeklyWarehouseClientPerformance(SQLModel, table=True):
    """One idempotent weekly KPI row for a warehouse/client pair."""

    __tablename__ = "weekly_warehouse_client_performance"
    __table_args__: ClassVar[tuple[SchemaItem | dict[str, str], ...]] = (
        UniqueConstraint("warehouse", "client_id", "week_start", name="uq_wwcp_warehouse_client_week"),
        CheckConstraint(
            "warehouse IN ('los_angeles', 'zaragoza')",
            name="ck_wwcp_warehouse",
        ),
        CheckConstraint(
            "inbound_units_count >= 0 AND outbound_orders_count >= 0 "
            "AND stockout_events_count >= 0 AND discrepancy_events_count >= 0",
            name="ck_wwcp_counts",
        ),
        CheckConstraint("discrepancy_rate >= 0 AND discrepancy_rate <= 1", name="ck_wwcp_rate"),
        CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="ck_wwcp_week_is_monday"),
        Index("ix_wwcp_week_start", "week_start"),
        {"schema": REPORTING_SCHEMA},
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )
    warehouse: str = Field(sa_column=Column(Text, nullable=False))
    client_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("clients.id", name="fk_wwcp_client_id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    week_start: date = Field(sa_column=Column(Date, nullable=False))
    inbound_units_count: int = Field(default=0, nullable=False)
    outbound_orders_count: int = Field(default=0, nullable=False)
    stockout_events_count: int = Field(default=0, nullable=False)
    discrepancy_events_count: int = Field(default=0, nullable=False)
    discrepancy_rate: Decimal = Field(default=Decimal(0), sa_column=Column(Numeric, nullable=False))
    computed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SourceLedgerState(SQLModel, table=True):
    """Singleton reset boundary used to distinguish recomputable source history."""

    __tablename__ = "source_ledger_state"
    __table_args__: ClassVar[tuple[SchemaItem | dict[str, str], ...]] = (
        CheckConstraint(f"id = {SOURCE_LEDGER_STATE_ID}", name="ck_source_ledger_state_singleton"),
        {"schema": REPORTING_SCHEMA},
    )

    id: int = Field(
        default=SOURCE_LEDGER_STATE_ID,
        sa_column=Column(SmallInteger, primary_key=True, nullable=False),
    )
    last_reset_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class IncompleteWeek(SQLModel, table=True):
    """A reset-interrupted ISO week that must never be presented as verified."""

    __tablename__ = "incomplete_weeks"
    __table_args__: ClassVar[tuple[SchemaItem | dict[str, str], ...]] = (
        CheckConstraint("EXTRACT(ISODOW FROM week_start) = 1", name="ck_incomplete_weeks_monday"),
        {"schema": REPORTING_SCHEMA},
    )

    week_start: date = Field(sa_column=Column(Date, primary_key=True, nullable=False))
    reason: str = Field(sa_column=Column(Text, nullable=False))
    recorded_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class PipelineRun(SQLModel, table=True):
    """Durable run request, worker lease, retry state, and sanitized audit record."""

    __tablename__ = "pipeline_runs"
    __table_args__: ClassVar[tuple[SchemaItem | dict[str, str], ...]] = (
        CheckConstraint(
            "trigger_type IN ('scheduled', 'manual', 'cli')",
            name="ck_pipeline_runs_trigger_type",
        ),
        CheckConstraint(
            "status IN ('requested', 'running', 'retryable', 'succeeded', 'failed')",
            name="ck_pipeline_runs_status",
        ),
        CheckConstraint("attempt >= 0", name="ck_pipeline_runs_attempt_nonnegative"),
        CheckConstraint(
            "error_code IS NULL OR error_code IN "
            "('EXTRACT_FAILED', 'VALIDATE_FAILED', 'LOAD_FAILED', 'DB_UNAVAILABLE', "
            "'LOCK_UNAVAILABLE', 'STALE_ABANDONED', 'MAX_ATTEMPTS_EXCEEDED')",
            name="ck_pipeline_runs_error_code",
        ),
        CheckConstraint(
            "(rows_extracted IS NULL OR rows_extracted >= 0) "
            "AND (rows_transformed IS NULL OR rows_transformed >= 0) "
            "AND (rows_loaded IS NULL OR rows_loaded >= 0)",
            name="ck_pipeline_runs_row_counts_nonnegative",
        ),
        Index(
            "uq_pipeline_runs_scheduled_date",
            "pipeline_name",
            "scheduled_business_date",
            unique=True,
            postgresql_where=text("trigger_type = 'scheduled'"),
        ),
        Index(
            "uq_pipeline_runs_single_active",
            "pipeline_name",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "uq_pipeline_runs_pending_manual",
            "pipeline_name",
            text("COALESCE(requested_week_start, '0001-01-01'::date)"),
            unique=True,
            postgresql_where=text(
                "status = 'requested' AND trigger_type = 'manual' AND cache_nonce IS NULL"
            ),
        ),
        Index("ix_pipeline_runs_claim", "pipeline_name", "status", "next_attempt_at", "requested_at"),
        Index("ix_pipeline_runs_latest", "pipeline_name", text("requested_at DESC")),
        {"schema": REPORTING_SCHEMA},
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )
    pipeline_name: str = Field(sa_column=Column(Text, nullable=False))
    pipeline_version: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    trigger_type: str = Field(sa_column=Column(String(16), nullable=False))
    requested_by: str = Field(sa_column=Column(Text, nullable=False))
    scheduled_business_date: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    requested_week_start: date | None = Field(default=None, sa_column=Column(Date, nullable=True))
    target_weeks: list[date] | None = Field(default=None, sa_column=Column(ARRAY(Date), nullable=True))
    source_window_start: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    source_window_end: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    requested_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    started_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    finished_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    attempt: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    next_attempt_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    claim_token: UUID | None = Field(default=None, sa_column=Column(PGUUID(as_uuid=True), nullable=True))
    heartbeat_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    lease_expires_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    cache_nonce: UUID | None = Field(default=None, sa_column=Column(PGUUID(as_uuid=True), nullable=True))
    rows_extracted: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    rows_transformed: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    rows_loaded: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    source_watermark: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    error_code: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    error_summary: str | None = Field(default=None, sa_column=Column(String(500), nullable=True))
