"""SQLModel persistence for the self-hosted agent trace store (Engagement 8).

Three related tables record one graph invocation:

* ``agent_run``       — one row per graph invocation (status, route, timing, token/cost totals).
* ``agent_node_step`` — one row per node executed (timing, status, per-step token/cost).
* ``agent_tool_call`` — one row per tool invocation (status, timing) — populated from Part 2 on.

Only PII-free, allowlisted metadata and REDACTED/truncated ``*_summary`` fields are stored. Raw
prompts, completions, retrieved text, tool arguments, credentials, addresses, and carrier rates
never enter these tables (telemetry standard §8). Rows are pruned by retention (see AgentRepository).
"""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel

RUN_STATUS_VALUES: tuple[str, ...] = ("ok", "error", "rejected")
STEP_STATUS_VALUES: tuple[str, ...] = ("ok", "error", "skipped")
TOOL_STATUS_VALUES: tuple[str, ...] = ("ok", "timeout", "error", "denied")


def utc_now() -> datetime:
    return datetime.now(UTC)


class AgentRun(SQLModel, table=True):
    """One agent graph invocation, keyed by a unique trace id."""

    __tablename__ = "agent_runs"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("status IN ('ok', 'error', 'rejected')", name="ck_agent_runs_status"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_runs_duration"),
        Index("ix_agent_runs_created_at", "created_at"),
        Index("ix_agent_runs_agent_status_created_at", "agent_name", "status", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    trace_id: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    agent_name: str = Field(sa_column=Column(String(64), nullable=False))
    env: str = Field(sa_column=Column(String(16), nullable=False))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    route_taken: str | None = Field(default=None, sa_column=Column(String(32), nullable=True))
    started_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    total_tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    total_cost_usd: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    guardrail_trigger_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    input_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    output_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )


class AgentNodeStep(SQLModel, table=True):
    """One node execution within a run, in graph order."""

    __tablename__ = "agent_node_steps"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("status IN ('ok', 'error', 'skipped')", name="ck_agent_node_steps_status"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_node_steps_duration"),
        Index("ix_agent_node_steps_run_id_sequence", "run_id", "sequence"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(
        sa_column=Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    )
    parent_step_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("agent_node_steps.id", ondelete="CASCADE"), nullable=True),
    )
    node_name: str = Field(sa_column=Column(String(64), nullable=False))
    sequence: int = Field(sa_column=Column(Integer, nullable=False))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    started_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    ended_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    duration_ms: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    tokens: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    cost_usd: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class AgentToolCall(SQLModel, table=True):
    """One tool invocation within a run (populated from Part 2 onward)."""

    __tablename__ = "agent_tool_calls"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint(
            "status IN ('ok', 'timeout', 'error', 'denied')", name="ck_agent_tool_calls_status"
        ),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_tool_calls_duration"),
        Index("ix_agent_tool_calls_run_id", "run_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(
        sa_column=Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False)
    )
    step_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("agent_node_steps.id", ondelete="SET NULL"), nullable=True),
    )
    tool_name: str = Field(sa_column=Column(String(64), nullable=False))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    duration_ms: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    error_type: str | None = Field(default=None, sa_column=Column(String(48), nullable=True))
    input_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    output_summary: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
