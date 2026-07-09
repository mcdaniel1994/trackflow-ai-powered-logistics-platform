"""Authenticated, aggregates-only HTTP boundary for telemetry reporting.

Every endpoint requires an authenticated Back Office session and returns bounded
aggregates. No endpoint exposes raw telemetry rows or any PII.
"""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.dependencies import current_principal
from ...db.session import get_session
from .schemas import AccessDenialMetrics, DispatchMetrics, ReceivingMetrics, StockLossMetrics
from .service import TelemetryService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

FromDate = Annotated[date, Query(alias="from")]
ToDate = Annotated[date, Query(alias="to")]


def telemetry_service(session: Annotated[Session, Depends(get_session)]) -> TelemetryService:
    return TelemetryService(session)


@router.get("/metrics/dispatch", response_model=DispatchMetrics)
def dispatch_metrics(
    from_date: FromDate,
    to_date: ToDate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[TelemetryService, Depends(telemetry_service)],
) -> DispatchMetrics:
    return service.dispatch_metrics(from_date, to_date)


@router.get("/metrics/receiving", response_model=ReceivingMetrics)
def receiving_metrics(
    from_date: FromDate,
    to_date: ToDate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[TelemetryService, Depends(telemetry_service)],
) -> ReceivingMetrics:
    return service.receiving_metrics(from_date, to_date)


@router.get("/metrics/stock-loss", response_model=StockLossMetrics)
def stock_loss_metrics(
    from_date: FromDate,
    to_date: ToDate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[TelemetryService, Depends(telemetry_service)],
) -> StockLossMetrics:
    return service.stock_loss_metrics(from_date, to_date)


@router.get("/metrics/access-denials", response_model=AccessDenialMetrics)
def access_denial_metrics(
    from_date: FromDate,
    to_date: ToDate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[TelemetryService, Depends(telemetry_service)],
) -> AccessDenialMetrics:
    return service.access_denial_metrics(from_date, to_date)
