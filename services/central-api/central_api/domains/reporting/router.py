"""Authenticated HTTP boundary for business reports and pipeline requests."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .schemas import PipelineRunAccepted, PipelineRunRequest, PipelineRunsResponse, WeeklyPerformanceResponse
from .service import ReportingService

router = APIRouter(prefix="/reporting", tags=["reporting"])


def reporting_service(session: Annotated[Session, Depends(get_session)]) -> ReportingService:
    return ReportingService(session)


@router.get("/weekly-warehouse-client-performance", response_model=WeeklyPerformanceResponse)
def weekly_performance(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ReportingService, Depends(reporting_service)],
    week_start: Annotated[str | None, Query()] = None,
) -> WeeklyPerformanceResponse:
    return service.weekly_performance(week_start)


@router.get("/pipeline-runs/latest", response_model=PipelineRunsResponse)
def latest_pipeline_runs(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[ReportingService, Depends(reporting_service)],
) -> PipelineRunsResponse:
    return service.latest_runs()


@router.post("/pipeline-runs", response_model=PipelineRunAccepted, status_code=status.HTTP_202_ACCEPTED)
def request_pipeline_run(
    payload: PipelineRunRequest,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[ReportingService, Depends(reporting_service)],
) -> PipelineRunAccepted:
    return service.request_run(
        week_start=payload.week_start,
        force_refresh=payload.force_refresh,
        requested_by=principal.user_id,
        role=principal.role,
    )
