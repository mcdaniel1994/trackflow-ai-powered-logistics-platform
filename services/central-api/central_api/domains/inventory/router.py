"""Thin HTTP boundary for the exact Engagement 5 inventory routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .schemas import (
    MovementPage,
    ProductPage,
    SKUCreate,
    SKURead,
    StockEntryCreate,
    StockEntryRead,
    StockExitCreate,
    StockExitRead,
)
from .service import InventoryService

router = APIRouter(prefix="/inventory", tags=["inventory"])


def inventory_service(session: Annotated[Session, Depends(get_session)]) -> InventoryService:
    """Bind one request-scoped database session to the inventory service."""
    return InventoryService(session)


@router.get("/products", response_model=ProductPage)
def list_products(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ProductPage:
    return service.list_products(limit=limit, offset=offset)


@router.post("/products", response_model=SKURead, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: SKUCreate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> SKURead:
    return service.create_sku(payload)


@router.get("/products/{sku_id}", response_model=SKURead)
def get_product(
    sku_id: int,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> SKURead:
    return service.get_product(sku_id)


@router.post("/orders/inbound", response_model=StockEntryRead, status_code=status.HTTP_201_CREATED)
def create_inbound_order(
    payload: StockEntryCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> StockEntryRead:
    # Identity is server-derived; user_uuid is deliberately absent from the request schema.
    return service.record_inbound(payload, principal.user_id)


@router.post("/orders/outbound", response_model=StockExitRead, status_code=status.HTTP_201_CREATED)
def create_outbound_order(
    payload: StockExitCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> StockExitRead:
    return service.record_outbound(payload, principal.user_id)


@router.get("/orders", response_model=MovementPage)
def list_orders(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MovementPage:
    return service.list_movements(limit=limit, offset=offset)
