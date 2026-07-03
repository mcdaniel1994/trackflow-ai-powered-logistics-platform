"""Authenticated supplier HTTP boundary."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlmodel import Session
from trackflow_auth import AuthenticatedPrincipal  # type: ignore[import-untyped]

from ...core.dependencies import current_principal, write_principal
from ...db.session import get_session
from .constants import COUNTRY_CURRENCY, VALID_CATEGORIES
from .schemas import RateUpdate, StatusUpdate, SupplierContact, SupplierCreate, SupplierPublic
from .service import SupplierError, SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def supplier_service(session: Annotated[Session, Depends(get_session)]) -> SupplierService:
    return SupplierService(session)


@router.post("", response_model=SupplierPublic, status_code=status.HTTP_201_CREATED)
def create_supplier(
    payload: SupplierCreate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
) -> SupplierPublic:
    return service.create(payload)


@router.get("", response_model=list[SupplierPublic])
def list_suppliers(
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
    country: Annotated[str | None, Query()] = None,
    category: Annotated[str | None, Query()] = None,
) -> list[SupplierPublic]:
    if country is not None and country not in COUNTRY_CURRENCY:
        raise SupplierError(400, "Country filter must be USA or Spain")
    if category is not None and category not in VALID_CATEGORIES:
        raise SupplierError(400, "Category filter is not valid")
    return service.list(country, category)


@router.get("/{supplier_id}", response_model=SupplierPublic)
def get_supplier(
    supplier_id: str,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
) -> SupplierPublic:
    return service.get(supplier_id)


@router.get("/{supplier_id}/contact", response_model=SupplierContact)
def supplier_contact(
    supplier_id: str,
    _principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
) -> SupplierContact:
    return service.contact(supplier_id)


@router.patch("/{supplier_id}/rate", response_model=SupplierPublic)
def update_rate(
    supplier_id: str,
    payload: RateUpdate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
) -> SupplierPublic:
    return service.update_rate(supplier_id, payload)


@router.patch("/{supplier_id}/status", response_model=SupplierPublic)
def update_status(
    supplier_id: str,
    payload: StatusUpdate,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
) -> SupplierPublic:
    return service.update_status(supplier_id, payload)


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_supplier(
    supplier_id: str,
    _principal: Annotated[AuthenticatedPrincipal, Depends(write_principal)],
    service: Annotated[SupplierService, Depends(supplier_service)],
) -> Response:
    service.delete(supplier_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
