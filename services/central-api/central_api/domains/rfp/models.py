"""SQLModel persistence for the RFP agentic workflow (Engagement 9).

Three related tables record one RFP proposal:

* ``rfp_tickets``              — one row per uploaded document: lifecycle status plus the safe
  extracted metadata (client, country, currency, requested services, routing decision) and the
  converted Markdown. Raw PDF bytes are never stored (owner decision; telemetry standard §8).
* ``rfp_department_sections`` — one row per active department: its key aspects, draft, evaluation
  results, iteration count, and human approval outcome.
* ``rfp_final_documents``     — one row per completed ticket: the consolidated approved sections.

Node-level execution traceability reuses the Engagement 8 agent trace store
(``agent_runs`` / ``agent_node_steps``) rather than a parallel audit table. Only PII-free,
never-store-safe values reach these tables: no addresses, warehouse routes, negotiated carrier
rates, credentials, prompts, tool arguments, or raw retrieved passages.
"""

from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import uuid4

from sqlalchemy import (
    JSON,
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
)
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel

# Ticket lifecycle. ``discarded`` is the explicit non-RFP / rejected terminal state (never silent).
TICKET_STATUS_VALUES: tuple[str, ...] = (
    "analyzing",
    "waiting_for_approval",
    "drafting",
    "under_evaluation",
    "done",
    "discarded",
)
DEPARTMENT_VALUES: tuple[str, ...] = ("warehouse", "lastmile", "reverse")
APPROVAL_STATUS_VALUES: tuple[str, ...] = ("pending", "approved", "rejected", "changes_requested")
COUNTRY_VALUES: tuple[str, ...] = ("US", "ES")
CURRENCY_VALUES: tuple[str, ...] = ("USD", "EUR")

_TICKET_STATUS_SQL = ", ".join(f"'{v}'" for v in TICKET_STATUS_VALUES)
_DEPARTMENT_SQL = ", ".join(f"'{v}'" for v in DEPARTMENT_VALUES)
_APPROVAL_SQL = ", ".join(f"'{v}'" for v in APPROVAL_STATUS_VALUES)


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_uuid() -> str:
    return str(uuid4())


class RfpTicket(SQLModel, table=True):
    """One uploaded RFP and its extracted, safe workflow metadata."""

    __tablename__ = "rfp_tickets"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint(f"status IN ({_TICKET_STATUS_SQL})", name="ck_rfp_tickets_status"),
        CheckConstraint("client_country IS NULL OR client_country IN ('US', 'ES')", name="ck_rfp_tickets_country"),
        CheckConstraint("currency IS NULL OR currency IN ('USD', 'EUR')", name="ck_rfp_tickets_currency"),
        CheckConstraint(
            "operator_jurisdiction IS NULL OR operator_jurisdiction IN ('US', 'ES')",
            name="ck_rfp_tickets_operator_jurisdiction",
        ),
        CheckConstraint("monthly_volume IS NULL OR monthly_volume >= 0", name="ck_rfp_tickets_volume"),
        CheckConstraint("deadline_days IS NULL OR deadline_days >= 0", name="ck_rfp_tickets_deadline"),
        Index("ix_rfp_tickets_owner_updated", "owner_user_uuid", "updated_at"),
        Index("ix_rfp_tickets_status_updated", "status", "updated_at"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=Column(String(36), primary_key=True))
    rfp_id: str = Field(sa_column=Column(String(64), nullable=False, unique=True))
    status: str = Field(sa_column=Column(String(24), nullable=False))
    owner_user_uuid: str = Field(sa_column=Column(String(36), nullable=False))
    # Server-derived operator jurisdiction (authorization/guardrail context); distinct from the
    # untrusted client_country extracted from the document.
    operator_jurisdiction: str | None = Field(default=None, sa_column=Column(String(2), nullable=True))
    client_name: str | None = Field(default=None, sa_column=Column(String(200), nullable=True))
    client_country: str | None = Field(default=None, sa_column=Column(String(2), nullable=True))
    currency: str | None = Field(default=None, sa_column=Column(String(3), nullable=True))
    services_requested: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    monthly_volume: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    deadline_days: int | None = Field(default=None, sa_column=Column(Integer, nullable=True))
    budget_range: str | None = Field(default=None, sa_column=Column(String(120), nullable=True))
    departments_needed: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    readability_grade: float | None = Field(default=None, sa_column=Column(Float, nullable=True))
    readability_metrics: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    markdown_text: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    discard_reason: str | None = Field(default=None, sa_column=Column(String(200), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RfpDepartmentSection(SQLModel, table=True):
    """One active department's contribution to a proposal and its human approval outcome."""

    __tablename__ = "rfp_department_sections"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint(f"department_id IN ({_DEPARTMENT_SQL})", name="ck_rfp_sections_department"),
        CheckConstraint(f"approval_status IN ({_APPROVAL_SQL})", name="ck_rfp_sections_approval_status"),
        CheckConstraint("iteration_count >= 0", name="ck_rfp_sections_iterations"),
        UniqueConstraint("ticket_id", "department_id", name="uq_rfp_sections_ticket_department"),
        Index("ix_rfp_sections_ticket", "ticket_id"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=Column(String(36), primary_key=True))
    ticket_id: str = Field(
        sa_column=Column(String(36), ForeignKey("rfp_tickets.id", ondelete="CASCADE"), nullable=False)
    )
    department_id: str = Field(sa_column=Column(String(16), nullable=False))
    key_aspects: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    draft_content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    evaluation_results: dict[str, Any] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    iteration_count: int = Field(default=0, sa_column=Column(Integer, nullable=False))
    approval_status: str = Field(default="pending", sa_column=Column(String(24), nullable=False))
    approver: str | None = Field(default=None, sa_column=Column(String(120), nullable=True))
    approved_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class RfpFinalDocument(SQLModel, table=True):
    """The consolidated proposal, generated only after every active department has approved."""

    __tablename__ = "rfp_final_documents"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("currency IN ('USD', 'EUR')", name="ck_rfp_final_currency"),
        UniqueConstraint("ticket_id", name="uq_rfp_final_ticket"),
    )

    id: str = Field(default_factory=new_uuid, sa_column=Column(String(36), primary_key=True))
    ticket_id: str = Field(
        sa_column=Column(String(36), ForeignKey("rfp_tickets.id", ondelete="CASCADE"), nullable=False)
    )
    sections: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False))
    generated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
