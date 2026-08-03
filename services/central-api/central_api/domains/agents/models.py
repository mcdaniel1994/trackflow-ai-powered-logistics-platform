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
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
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
    run_id: int = Field(sa_column=Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False))
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
        CheckConstraint("status IN ('ok', 'timeout', 'error', 'denied')", name="ck_agent_tool_calls_status"),
        CheckConstraint("duration_ms IS NULL OR duration_ms >= 0", name="ck_agent_tool_calls_duration"),
        Index("ix_agent_tool_calls_run_id", "run_id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(sa_column=Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False))
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


class AgentGuardrailEvent(SQLModel, table=True):
    """Allowlisted intervention metadata; rejected content is never stored."""

    __tablename__ = "agent_guardrail_events"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("category IN ('structural', 'content', 'security')", name="ck_agent_guardrail_category"),
        CheckConstraint(
            "outcome IN ('allowed', 'blocked', 'redirected', 'clarification')",
            name="ck_agent_guardrail_outcome",
        ),
        CheckConstraint("duration_ms >= 0", name="ck_agent_guardrail_duration"),
        Index("ix_agent_guardrail_rule_created_at", "rule_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(sa_column=Column(Integer, ForeignKey("agent_runs.id", ondelete="CASCADE"), nullable=False))
    layer: str = Field(sa_column=Column(String(32), nullable=False))
    rule_id: str = Field(sa_column=Column(String(64), nullable=False))
    category: str = Field(sa_column=Column(String(16), nullable=False))
    outcome: str = Field(sa_column=Column(String(16), nullable=False))
    duration_ms: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


MEMORY_KINDS: tuple[str, ...] = (
    "carrier_coverage_correction",
    "carrier_assignment_correction",
    "recurring_operational_pattern",
    "carrier_b2b_reporting_preference",
)


class AgentConversation(SQLModel, table=True):
    """Durable owner boundary for a sequence of agent turns."""

    __tablename__ = "agent_conversations"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("jurisdiction IN ('US', 'ES')", name="ck_agent_conversations_jurisdiction"),
        Index("ix_agent_conversations_owner_updated", "owner_user_uuid", "updated_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    owner_user_uuid: str = Field(sa_column=Column(String(36), nullable=False))
    jurisdiction: str = Field(sa_column=Column(String(2), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AgentMemoryProposal(SQLModel, table=True):
    """One human-visible, validated candidate awaiting a typed decision."""

    __tablename__ = "agent_memory_proposals"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'discarded')",
            name="ck_agent_memory_proposals_status",
        ),
        CheckConstraint("jurisdiction IN ('US', 'ES')", name="ck_agent_memory_proposals_jurisdiction"),
        CheckConstraint(
            "kind IN ('carrier_coverage_correction', 'carrier_assignment_correction', "
            "'recurring_operational_pattern', 'carrier_b2b_reporting_preference')",
            name="ck_agent_memory_proposals_kind",
        ),
        CheckConstraint("recurrence_count >= 2", name="ck_agent_memory_proposals_recurrence"),
        Index(
            "uq_agent_memory_proposals_one_pending",
            "conversation_id",
            unique=True,
            postgresql_where=text("status = 'pending'"),
        ),
        Index("ix_agent_memory_proposals_pending_updated", "status", "updated_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    conversation_id: str = Field(
        sa_column=Column(
            String(36),
            ForeignKey("agent_conversations.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    carrier_id: str = Field(sa_column=Column(String(36), ForeignKey("suppliers.id"), nullable=False))
    jurisdiction: str = Field(sa_column=Column(String(2), nullable=False))
    kind: str = Field(sa_column=Column(String(48), nullable=False))
    subject_key: str = Field(sa_column=Column(String(160), nullable=False))
    fact: str = Field(sa_column=Column(Text, nullable=False))
    recurrence_count: int = Field(sa_column=Column(Integer, nullable=False))
    effective_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    status: str = Field(default="pending", sa_column=Column(String(16), nullable=False))
    trace_id: str = Field(sa_column=Column(String(64), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    decided_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))


class AgentMemoryFact(SQLModel, table=True):
    """Consolidated active structured memory, unique by carrier/jurisdiction/subject."""

    __tablename__ = "agent_memory_facts"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("jurisdiction IN ('US', 'ES')", name="ck_agent_memory_facts_jurisdiction"),
        CheckConstraint(
            "kind IN ('carrier_coverage_correction', 'carrier_assignment_correction', "
            "'recurring_operational_pattern', 'carrier_b2b_reporting_preference')",
            name="ck_agent_memory_facts_kind",
        ),
        CheckConstraint("recurrence_count >= 2", name="ck_agent_memory_facts_recurrence"),
        CheckConstraint("confirmation_count >= 1", name="ck_agent_memory_facts_confirmations"),
        CheckConstraint("version >= 1", name="ck_agent_memory_facts_version"),
        UniqueConstraint(
            "carrier_id",
            "jurisdiction",
            "kind",
            "subject_key",
            name="uq_agent_memory_facts_consolidation",
        ),
        Index("ix_agent_memory_facts_carrier_jurisdiction_active", "carrier_id", "jurisdiction", "active"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    carrier_id: str = Field(sa_column=Column(String(36), ForeignKey("suppliers.id"), nullable=False))
    jurisdiction: str = Field(sa_column=Column(String(2), nullable=False))
    kind: str = Field(sa_column=Column(String(48), nullable=False))
    subject_key: str = Field(sa_column=Column(String(160), nullable=False))
    fact: str = Field(sa_column=Column(Text, nullable=False))
    recurrence_count: int = Field(sa_column=Column(Integer, nullable=False))
    effective_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    confirmation_count: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    version: int = Field(default=1, sa_column=Column(Integer, nullable=False))
    active: bool = Field(default=True, sa_column=Column(Boolean, nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AgentMemoryDecision(SQLModel, table=True):
    """Append-only safe decision record; no message or candidate payload is stored."""

    __tablename__ = "agent_memory_decisions"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("action IN ('approve', 'reject', 'edit')", name="ck_agent_memory_decisions_action"),
        Index("ix_agent_memory_decisions_conversation_created", "conversation_id", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    decision_id: str = Field(sa_column=Column(String(36), nullable=False, unique=True))
    proposal_id: str = Field(sa_column=Column(String(36), nullable=False))
    conversation_id: str = Field(sa_column=Column(String(36), ForeignKey("agent_conversations.id"), nullable=False))
    actor_user_uuid: str = Field(sa_column=Column(String(36), nullable=False))
    trace_id: str = Field(sa_column=Column(String(64), nullable=False))
    action: str = Field(sa_column=Column(String(16), nullable=False))
    outcome: str = Field(sa_column=Column(String(32), nullable=False))
    reason_code: str = Field(sa_column=Column(String(48), nullable=False))
    fact_id: str | None = Field(default=None, sa_column=Column(String(36), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class AgentMemoryVersion(SQLModel, table=True):
    """Append-only fact snapshot for every approved consolidation version."""

    __tablename__ = "agent_memory_versions"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        UniqueConstraint("fact_id", "version", name="uq_agent_memory_versions_fact_version"),
        CheckConstraint("version >= 1", name="ck_agent_memory_versions_version"),
    )

    id: int | None = Field(default=None, primary_key=True)
    fact_id: str = Field(sa_column=Column(String(36), ForeignKey("agent_memory_facts.id"), nullable=False))
    version: int = Field(sa_column=Column(Integer, nullable=False))
    carrier_id: str = Field(sa_column=Column(String(36), nullable=False))
    jurisdiction: str = Field(sa_column=Column(String(2), nullable=False))
    kind: str = Field(sa_column=Column(String(48), nullable=False))
    subject_key: str = Field(sa_column=Column(String(160), nullable=False))
    fact: str = Field(sa_column=Column(Text, nullable=False))
    recurrence_count: int = Field(sa_column=Column(Integer, nullable=False))
    effective_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    actor_user_uuid: str = Field(sa_column=Column(String(36), nullable=False))
    proposal_id: str = Field(sa_column=Column(String(36), nullable=False))
    decision_id: str = Field(sa_column=Column(String(36), nullable=False))
    trace_id: str = Field(sa_column=Column(String(64), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
