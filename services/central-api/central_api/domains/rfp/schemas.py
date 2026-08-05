"""HTTP read models for the RFP workflow.

Outbound-only in Phase 0: the list and detail views the Back Office RFP Desk renders. Upload and
decision request bodies arrive with the intake (Phase 1) and approval (Phase 3) work. These models
expose only safe, extracted metadata — never the raw uploaded bytes or provider internals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class RfpDepartmentSectionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    department_id: str
    approval_status: str
    iteration_count: int
    key_aspects: dict[str, Any] | None = None
    evaluation_results: dict[str, Any] | None = None
    approver: str | None = None
    approved_at: datetime | None = None
    updated_at: datetime


class RfpTicketSummary(BaseModel):
    """One row in the RFP Desk list view."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    rfp_id: str
    status: str
    client_name: str | None = None
    client_country: str | None = None
    currency: str | None = None
    departments_needed: list[str] | None = None
    created_at: datetime
    updated_at: datetime


class RfpTicketDetail(RfpTicketSummary):
    """Full ticket view, including per-department sections and safe intake metadata."""

    services_requested: list[str] | None = None
    monthly_volume: int | None = None
    deadline_days: int | None = None
    budget_range: str | None = None
    readability_grade: float | None = None
    discard_reason: str | None = None
    sections: list[RfpDepartmentSectionRead] = []


class RfpFinalDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    ticket_id: str
    currency: str
    sections: dict[str, Any]
    generated_at: datetime
