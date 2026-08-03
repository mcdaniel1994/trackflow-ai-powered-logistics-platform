"""Authenticated HTTP boundary for the LangGraph agent and its trace store.

``POST /agent/query`` invokes the graph only (no business logic here). ``GET /agents/runs`` and
``GET /agents/runs/{trace_id}`` serve the Agent OS dashboard from the self-hosted trace store.
The query endpoint requires a write principal (and CSRF for cookie auth, since it triggers paid
provider calls); the read endpoints require an authenticated principal.
"""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal, extract_access_token  # type: ignore[import-untyped]

from ...core.config import Settings, get_settings
from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .schemas import AgentQueryRequest, AgentQueryResponse, GuardrailSummary, RunDetail, RunSummary
from .service import AgentService

router = APIRouter(tags=["agents"])


def _require_admin(principal: AuthenticatedPrincipal) -> None:
    if principal.role != "admin":
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin role required")


def _query_service(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> AgentService:
    return AgentService(settings, session)


def _read_service(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[Session, Depends(get_session)],
) -> AgentService:
    return AgentService(settings, session)


@router.post("/agent/query", response_model=AgentQueryResponse)
def query_agent(
    payload: AgentQueryRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[AgentService, Depends(_query_service)],
) -> AgentQueryResponse:
    return service.answer(payload, background_tasks, extract_access_token(request), principal)


@router.get("/agents/runs", response_model=list[RunSummary])
def list_agent_runs(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[AgentService, Depends(_read_service)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    agent_name: str | None = None,
    status: str | None = None,
) -> list[RunSummary]:
    return service.list_runs(limit=limit, agent_name=agent_name, status=status)


@router.get("/agents/runs/{trace_id}", response_model=RunDetail)
def get_agent_run(
    trace_id: str,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[AgentService, Depends(_read_service)],
) -> RunDetail:
    return service.get_run(trace_id)


@router.get("/agents/guardrails/summary", response_model=list[GuardrailSummary])
def guardrail_summary(
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[AgentService, Depends(_read_service)],
) -> list[GuardrailSummary]:
    _require_admin(principal)
    return service.guardrail_summary()
