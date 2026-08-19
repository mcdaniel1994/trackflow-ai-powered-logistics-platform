"""Authenticated HTTP boundary for the RFP workflow.

Phase 0 exposes owner-scoped reads for the Back Office RFP Desk. Upload (``POST /rfp/tickets``) and
per-department approval decisions arrive with later phases. Reads require an authenticated principal;
each ticket is scoped to its owner.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Query, Response, UploadFile
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.config import Settings, get_settings
from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from ..realtime.bus import RealtimeBus
from ..realtime.router import get_realtime_bus
from .schemas import DepartmentDecisionRequest, RfpFinalDocumentRead, RfpTicketDetail, RfpTicketSummary
from .service import RfpService

router = APIRouter(prefix="/rfp", tags=["rfp"])


def _service(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
    realtime_bus: Annotated[RealtimeBus, Depends(get_realtime_bus)],
) -> RfpService:
    return RfpService(settings, session, realtime_bus=realtime_bus)


@router.post("/tickets", response_model=RfpTicketSummary, status_code=202)
def upload_ticket(
    background_tasks: BackgroundTasks,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[RfpService, Depends(_service)],
    file: Annotated[UploadFile, File()],
) -> RfpTicketSummary:
    data = file.file.read()
    return service.create_from_upload(
        owner_user_uuid=principal.user_id,
        operator_jurisdiction=principal.jurisdiction,
        filename=file.filename,
        content_type=file.content_type,
        data=data,
        background_tasks=background_tasks,
    )


@router.get("/tickets", response_model=list[RfpTicketSummary])
def list_tickets(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RfpService, Depends(_service)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    status: str | None = None,
) -> list[RfpTicketSummary]:
    return service.list_tickets(principal.user_id, status=status, limit=limit)


@router.get("/tickets/{ticket_id}", response_model=RfpTicketDetail)
def get_ticket(
    ticket_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RfpService, Depends(_service)],
) -> RfpTicketDetail:
    return service.get_ticket(ticket_id, principal.user_id)


@router.post("/tickets/{ticket_id}/departments/{department_id}/decision", response_model=RfpTicketDetail)
def decide_department(
    ticket_id: str,
    department_id: str,
    payload: DepartmentDecisionRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[RfpService, Depends(_service)],
) -> RfpTicketDetail:
    return service.decide(
        ticket_id,
        department_id,
        action=payload.action,
        note=payload.note,
        actor=principal.user_id,
    )


@router.get("/tickets/{ticket_id}/document", response_model=RfpFinalDocumentRead)
def get_document(
    ticket_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RfpService, Depends(_service)],
) -> RfpFinalDocumentRead:
    return service.get_document(ticket_id, principal.user_id)


@router.get("/tickets/{ticket_id}/document/download")
def download_document(
    ticket_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RfpService, Depends(_service)],
) -> Response:
    """Download the finalized proposal as a Markdown attachment (server-generated filename)."""
    markdown, filename = service.get_document_markdown(ticket_id, principal.user_id)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/tickets/{ticket_id}/document/pdf")
def download_document_pdf(
    ticket_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[RfpService, Depends(_service)],
) -> Response:
    """Download the finalized proposal as a branded PDF attachment (server-generated filename)."""
    pdf_bytes, filename = service.get_document_pdf(ticket_id, principal.user_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
