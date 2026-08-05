"""RFP workflow service: the boundary between HTTP and persistence.

Phase 0 serves owner-scoped reads and enforces the feature gate. Intake (upload + graph),
generation, and approval land in later phases; the router stays thin and delegates here so that
authorization and the disabled-service fallback live in one place.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlmodel import Session

from ...core.config import Settings
from .config import is_rfp_configured
from .models import RfpTicket
from .repository import RfpRepository
from .schemas import RfpDepartmentSectionRead, RfpTicketDetail, RfpTicketSummary


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
