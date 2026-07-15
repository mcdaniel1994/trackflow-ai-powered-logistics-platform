"""Thin HTTP boundary for the exact Engagement 5 inventory routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .schemas import (
    ClientCreate,
    ClientRead,
    ClientUpdate,
    InventoryDiscrepancyCreate,
    InventoryDiscrepancyRead,
    MovementPage,
    ProductPage,
    SKUCreate,
    SKURead,
    SKUUpdate,
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


@router.get("/clients", response_model=list[ClientRead])
def list_clients(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> list[ClientRead]:
    return service.list_clients()


@router.post("/clients", response_model=ClientRead, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> ClientRead:
    return service.create_client(payload, principal.role)


@router.patch("/clients/{client_id}", response_model=ClientRead)
def rename_client(
    client_id: UUID,
    payload: ClientUpdate,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> ClientRead:
    return service.rename_client(client_id, payload, principal.role)


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


@router.patch("/products/{sku_id}", response_model=SKURead)
def update_product(
    sku_id: int,
    payload: SKUUpdate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> SKURead:
    return service.update_sku(sku_id, payload)


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


@router.post("/discrepancies", response_model=InventoryDiscrepancyRead, status_code=status.HTTP_201_CREATED)
def create_discrepancy(
    payload: InventoryDiscrepancyCreate,
    principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
) -> InventoryDiscrepancyRead:
    return service.record_discrepancy(payload, principal.user_id)


@router.get("/orders", response_model=MovementPage)
def list_orders(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[InventoryService, Depends(inventory_service)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> MovementPage:
    return service.list_movements(limit=limit, offset=offset)
