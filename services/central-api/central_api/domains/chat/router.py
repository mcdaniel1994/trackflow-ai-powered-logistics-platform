"""Authenticated, owner-scoped HTTP session history for the Phase 4 UI."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.config import Settings, get_settings
from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .schemas import ChatSessionDetail, ChatSessionRead
from .service import ChatService

router = APIRouter(prefix="/chat/sessions", tags=["chat"])


def _service(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> ChatService:
    return ChatService(settings, session)


@router.post("", response_model=ChatSessionRead, status_code=201)
def create_chat_session(
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[ChatService, Depends(_service)],
) -> ChatSessionRead:
    return service.create_session(user_id=principal.user_id, jurisdiction=principal.jurisdiction)


@router.get("", response_model=list[ChatSessionRead])
def list_chat_sessions(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ChatService, Depends(_service)],
) -> list[ChatSessionRead]:
    return service.list_sessions(user_id=principal.user_id)


@router.get("/{session_id}", response_model=ChatSessionDetail)
def get_chat_session(
    session_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ChatService, Depends(_service)],
) -> ChatSessionDetail:
    return service.get_session(session_id, user_id=principal.user_id)
