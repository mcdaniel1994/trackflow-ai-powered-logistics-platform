"""RFP workflow service: the boundary between HTTP and persistence.

Phase 0 serves owner-scoped reads and enforces the feature gate. Intake (upload + graph),
generation, and approval land in later phases; the router stays thin and delegates here so that
authorization and the disabled-service fallback live in one place.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from kombu.exceptions import OperationalError
from sqlmodel import Session

from ...core.config import Settings
from ..rag.config import build_rag_config
from ..realtime.bus import RealtimeBus, rfp_ticket_topic
from ..realtime.schemas import RfpTicketCreatedEvent
from ..tasks.dispatcher import enqueue_rfp_processing
from .approval import AlreadyResolved, submit_decision
from .config import is_rfp_configured, is_rfp_generation_configured, is_rfp_intake_configured
from .document import DocumentError, pdf_to_markdown
from .models import RfpFinalDocument, RfpTicket
from .pdf import render_final_document_pdf
from .readability import readability_dict
from .render import render_final_document
from .repository import RfpRepository
from .schemas import RfpDepartmentSectionRead, RfpFinalDocumentRead, RfpTaskAccepted, RfpTicketDetail, RfpTicketSummary

_PDF_CONTENT_TYPES = {"application/pdf", "application/x-pdf"}
logger = logging.getLogger(__name__)


def _new_rfp_id() -> str:
    return f"RFP-{uuid4().hex[:10].upper()}"


@dataclass
class RfpError(Exception):
    """Typed RFP failure translated to HTTP only at the application boundary."""

    status_code: int
    detail: str


class RfpService:
    def __init__(self, settings: Settings, session: Session, *, realtime_bus: RealtimeBus | None = None) -> None:
        self.settings = settings
        self.session = session
        self.repository = RfpRepository(session)
        self.realtime_bus = realtime_bus

    def _publish_ticket_created(self, ticket: RfpTicket) -> None:
        """Notify the ticket owner after commit without coupling creation to a consumer."""
        if self.realtime_bus is None:
            return
        payload = RfpTicketCreatedEvent(
            ticket_id=ticket.id,
            rfp_id=ticket.rfp_id,
            client_name=ticket.client_name,
            client_country=ticket.client_country,
            services_requested=list(ticket.services_requested or []),
            status=ticket.status,
            created_at=ticket.created_at,
        )
        try:
            self.realtime_bus.publish(
                rfp_ticket_topic(ticket.owner_user_uuid),
                "rfp_ticket_created",
                payload.model_dump(mode="json"),
            )
        except RuntimeError:
            logger.warning("RFP realtime notification unavailable", extra={"event_type": "rfp_ticket_created"})

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
    ) -> RfpTaskAccepted:
        """Convert an uploaded PDF, create an analyzing ticket, and enqueue independent intake."""
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
        try:
            enqueue_rfp_processing(ticket.id)
        except (OperationalError, OSError):
            self.repository.delete_ticket(ticket)
            raise RfpError(503, "The RFP task queue is unavailable right now.") from None
        self._publish_ticket_created(ticket)
        summary = RfpTicketSummary.model_validate(ticket)
        return RfpTaskAccepted(**summary.model_dump(), task_id=ticket.id)

    def decide(
        self,
        ticket_id: str,
        department_id: str,
        *,
        action: str,
        note: str | None,
        actor: str,
    ) -> RfpTicketDetail:
        """Record a human approve/reject/request-changes decision for one department."""
        if not is_rfp_generation_configured(self.settings):
            raise RfpError(503, "The RFP workflow is not available right now.")
        ticket = self.repository.get_for_owner(ticket_id, actor)
        if ticket is None:
            raise RfpError(404, "RFP ticket not found.")
        section = self.repository.section_for_department(ticket_id, department_id)
        if section is None:
            raise RfpError(404, "Department section not found.")
        rag_config = build_rag_config(self.settings)
        try:
            submit_decision(
                ticket,
                section,
                action=action,
                note=note,
                actor=actor,
                settings=self.settings,
                rag_config=rag_config,
                session=self.session,
                env=self.settings.app_env,
            )
        except AlreadyResolved:
            raise RfpError(409, "This department decision has already been recorded.") from None
        except ValueError:
            raise RfpError(400, "Unknown decision action.") from None
        return self.get_ticket(ticket_id, actor)

    def get_document(self, ticket_id: str, owner_user_uuid: str) -> RfpFinalDocumentRead:
        self._require_enabled()
        ticket = self.repository.get_for_owner(ticket_id, owner_user_uuid)
        if ticket is None:
            raise RfpError(404, "RFP ticket not found.")
        document = self.repository.final_document(ticket_id)
        if document is None:
            raise RfpError(404, "The final document is not ready yet.")
        return RfpFinalDocumentRead.model_validate(document)

    def get_document_markdown(self, ticket_id: str, owner_user_uuid: str) -> tuple[str, str]:
        """Render the finalized proposal as Markdown and a safe, server-generated filename.

        Reuses the exact ownership/readiness checks in ``get_document`` (404 for a missing/non-owned
        ticket, 404 when the document is not ready). The filename is derived only from the ticket UUID
        and the generation date — never from client input.
        """
        self._require_enabled()
        ticket = self.repository.get_for_owner(ticket_id, owner_user_uuid)
        if ticket is None:
            raise RfpError(404, "RFP ticket not found.")
        document = self.repository.final_document(ticket_id)
        if document is None:
            raise RfpError(404, "The final document is not ready yet.")
        sections = self.repository.sections_for_ticket(ticket_id)
        markdown = render_final_document(ticket, document, sections)
        return markdown, self._document_filename(ticket, document, "md")

    def get_document_pdf(self, ticket_id: str, owner_user_uuid: str) -> tuple[bytes, str]:
        """Render the finalized proposal to a branded PDF and a safe, server-generated filename.

        Same ownership/readiness 404s as ``get_document``. The PDF is produced on the fly and never
        persisted (consistent with the raw-bytes-never-persisted rule).
        """
        self._require_enabled()
        ticket = self.repository.get_for_owner(ticket_id, owner_user_uuid)
        if ticket is None:
            raise RfpError(404, "RFP ticket not found.")
        document = self.repository.final_document(ticket_id)
        if document is None:
            raise RfpError(404, "The final document is not ready yet.")
        sections = self.repository.sections_for_ticket(ticket_id)
        try:
            pdf_bytes = render_final_document_pdf(ticket, document, sections)
        except Exception as exc:  # WeasyPrint/native-lib failure must not leak a stack trace
            logger.warning("rfp_pdf_render_failed error_type=%s", type(exc).__name__)
            raise RfpError(503, "The proposal PDF could not be generated right now.") from None
        return pdf_bytes, self._document_filename(ticket, document, "pdf")

    @staticmethod
    def _document_filename(ticket: RfpTicket, document: RfpFinalDocument, ext: str) -> str:
        short_id = ticket.id.replace("-", "")[:8]
        stamp = document.generated_at.strftime("%Y%m%d")
        return f"trackflow-rfp-{short_id}-{stamp}.{ext}"

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
