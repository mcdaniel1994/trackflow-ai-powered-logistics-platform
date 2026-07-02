"""Authenticated HTTP boundary for centralized incident management."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]
from trackflow_incidents import Branch, IncidentCategory, IncidentOrigin, IncidentStatus

from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .schemas import IncidentCreate, IncidentPage, IncidentRead, IncidentStatusUpdate, IncidentSummary
from .service import IncidentService

router = APIRouter(prefix="/api/incidents", tags=["incidents"])


def incident_service(session: Annotated[Session, Depends(get_session)]) -> IncidentService:
    return IncidentService(session)


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED)
def create_incident(
    payload: IncidentCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[IncidentService, Depends(incident_service)],
) -> IncidentRead:
    return service.create(payload, principal.user_id)


@router.get("", response_model=IncidentPage)
def list_incidents(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IncidentService, Depends(incident_service)],
    incident_status: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    origin: IncidentOrigin | None = None,
    branch: Branch | None = None,
    category: IncidentCategory | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IncidentPage:
    return service.list(
        status=incident_status,
        origin=origin,
        branch=branch,
        category=category,
        limit=limit,
        offset=offset,
    )


@router.get("/summary", response_model=IncidentSummary)
def incident_summary(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IncidentService, Depends(incident_service)],
) -> IncidentSummary:
    return service.summary()


@router.get("/{incident_id}", response_model=IncidentRead)
def get_incident(
    incident_id: int,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[IncidentService, Depends(incident_service)],
) -> IncidentRead:
    return service.get(incident_id)


@router.patch("/{incident_id}/status", response_model=IncidentRead)
def update_incident_status(
    incident_id: int,
    payload: IncidentStatusUpdate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[IncidentService, Depends(incident_service)],
) -> IncidentRead:
    return service.update_status(incident_id, payload)

