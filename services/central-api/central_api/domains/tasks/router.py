"""Authenticated task-status API for DEV-55."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.dependencies import current_principal
from ...db.session import get_session
from .schemas import TaskStatusRead
from .service import TaskStatusService

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskStatusRead)
def task_status(
    task_id: str,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    session: Annotated[Session, Depends(get_session)],
) -> TaskStatusRead:
    return TaskStatusService(session).get(task_id, principal.user_id)
