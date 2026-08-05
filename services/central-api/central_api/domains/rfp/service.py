"""RFP workflow service: the boundary between HTTP and persistence.

Phase 0 serves owner-scoped reads and enforces the feature gate. Intake (upload + graph),
generation, and approval land in later phases; the router stays thin and delegates here so that
authorization and the disabled-service fallback live in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import BackgroundTasks
from sqlmodel import Session

from ...core.config import Settings
from .config import build_rfp_config, is_rfp_configured, is_rfp_intake_configured
from .document import DocumentError, pdf_to_markdown
from .intake import run_intake_for_ticket
from .models import RfpTicket
from .readability import readability_dict
from .repository import RfpRepository
from .schemas import RfpDepartmentSectionRead, RfpTicketDetail, RfpTicketSummary

_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}


def _new_rfp_id() -> str:
    return f"RFP-{uuid4().hex[:10].upper()}"


@dataclass
class RfpError(Exception):
    """Typed RFP failure translated to HTTP only at the application boundary."""

    status_code: int
    detail: str


class RfpService:
    def __init__(self, settings: Settings, session: Session) -> None:
        self.settings = settings
        self.repository = RfpRepository(session)

    def _require_enabled(self) -> None:
        if not is_rfp_configured(self.settings):
            raise RfpError(503, "The RFP workflow is not available right now.")

    def create_from_upload(
        self,
        *,
        owner_user_uuid: str,
        operator_jurisdiction: str | None,
        filename: str | None,
        content_type: str | None,
        data: bytes,
        background_tasks: BackgroundTasks,
    ) -> RfpTicketSummary:
        """Convert an uploaded PDF, create an analyzing ticket, and schedule background intake."""
        if not is_rfp_intake_configured(self.settings):
            raise RfpError(503, "The RFP workflow is not available right now.")
        is_pdf = (content_type in _PDF_CONTENT_TYPES) or bool(filename and filename.lower().endswith(".pdf"))
        if not is_pdf:
            raise RfpError(415, "Only PDF documents are accepted.")
        try:
            markdown = pdf_to_markdown(data)
        except DocumentError as exc:
            raise RfpError(400, exc.detail) from None

        metrics = readability_dict(markdown)
        ticket = self.repository.add_ticket(
            RfpTicket(
                rfp_id=_new_rfp_id(),
                status="analyzing",
                owner_user_uuid=owner_user_uuid,
                operator_jurisdiction=operator_jurisdiction,
                markdown_text=markdown,
                readability_grade=float(metrics["flesch_kincaid_grade"]),
                readability_metrics=dict(metrics),
            )
        )
        config = build_rfp_config(self.settings)
        background_tasks.add_task(run_intake_for_ticket, ticket.id, config, env=self.settings.app_env)
        return RfpTicketSummary.model_validate(ticket)

    def list_tickets(
        self,
        owner_user_uuid: str,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[RfpTicketSummary]:
        self._require_enabled()
        tickets = self.repository.list_for_owner(owner_user_uuid, status=status, limit=limit)
        return [RfpTicketSummary.model_validate(ticket) for ticket in tickets]

    def get_ticket(self, ticket_id: str, owner_user_uuid: str) -> RfpTicketDetail:
        self._require_enabled()
        ticket: RfpTicket | None = self.repository.get_for_owner(ticket_id, owner_user_uuid)
        if ticket is None:
            raise RfpError(404, "RFP ticket not found.")
        sections = self.repository.sections_for_ticket(ticket.id)
        detail = RfpTicketDetail.model_validate(ticket)
        detail.sections = [RfpDepartmentSectionRead.model_validate(section) for section in sections]
        return detail
