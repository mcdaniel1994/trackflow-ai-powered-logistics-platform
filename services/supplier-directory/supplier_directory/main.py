"""FastAPI app for the TrackFlow supplier directory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from trackflow_auth import AuthenticatedPrincipal, authenticate_request, require_csrf

from .config import get_auth_config, get_cors_origins, get_db_path
from .constants import COUNTRY_CURRENCY, VALID_CATEGORIES
from .models import RateUpdate, StatusUpdate, SupplierContact, SupplierCreate, SupplierPublic
from .repository import SupplierRepository
from .seed import SUPPLIERS_SEED
from .service import SupplierService


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repository = SupplierRepository(get_db_path())
        service = SupplierService(repository)
        app.state.supplier_service = service
        service.seed_if_empty(SUPPLIERS_SEED)
        try:
            yield
        finally:
            repository.close()

    app = FastAPI(title="TrackFlow Supplier Directory", version="0.1.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["*"],
    )

    def get_service() -> SupplierService:
        service = getattr(app.state, "supplier_service", None)
        if not isinstance(service, SupplierService):
            raise RuntimeError("Supplier service is not initialized.")
        return service

    def supplier_or_404(supplier_id: str) -> SupplierPublic:
        supplier = get_service().get_supplier(supplier_id)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return supplier

    # Verifies the Auth 1 access token for supplier business routes.
    def current_principal(request: Request) -> AuthenticatedPrincipal:
        return authenticate_request(request, get_auth_config())

    # Enforces CSRF only on cookie-backed state-changing supplier calls.
    def csrf_guard(request: Request) -> None:
        require_csrf(request, get_auth_config())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/suppliers", response_model=SupplierPublic, status_code=201)
    async def create_supplier(
        payload: SupplierCreate,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
        _csrf: None = Depends(csrf_guard),
    ) -> SupplierPublic:
        return get_service().create_supplier(payload)

    @app.get("/suppliers", response_model=list[SupplierPublic])
    async def list_suppliers(
        country: str | None = None,
        category: str | None = None,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
    ) -> list[SupplierPublic]:
        if country is not None and country not in COUNTRY_CURRENCY:
            raise HTTPException(status_code=400, detail="Country filter must be USA or Spain")
        if category is not None and category not in VALID_CATEGORIES:
            raise HTTPException(status_code=400, detail="Category filter is not valid")
        return get_service().list_suppliers(country=country, category=category)

    @app.get("/suppliers/{supplier_id}", response_model=SupplierPublic)
    async def get_supplier(
        supplier_id: str,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
    ) -> SupplierPublic:
        return supplier_or_404(supplier_id)

    @app.get("/suppliers/{supplier_id}/contact", response_model=SupplierContact)
    async def get_supplier_contact(
        supplier_id: str,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
    ) -> SupplierContact:
        contact = get_service().get_supplier_contact(supplier_id)
        if contact is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return contact

    @app.patch("/suppliers/{supplier_id}/rate", response_model=SupplierPublic)
    async def update_supplier_rate(
        supplier_id: str,
        payload: RateUpdate,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
        _csrf: None = Depends(csrf_guard),
    ) -> SupplierPublic:
        supplier = get_service().update_rate(supplier_id, payload)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return supplier

    @app.patch("/suppliers/{supplier_id}/status", response_model=SupplierPublic)
    async def update_supplier_status(
        supplier_id: str,
        payload: StatusUpdate,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
        _csrf: None = Depends(csrf_guard),
    ) -> SupplierPublic:
        supplier = get_service().update_status(supplier_id, payload)
        if supplier is None:
            raise HTTPException(status_code=404, detail="Supplier not found")
        return supplier

    @app.delete("/suppliers/{supplier_id}", status_code=204)
    async def delete_supplier(
        supplier_id: str,
        _principal: AuthenticatedPrincipal = Depends(current_principal),
        _csrf: None = Depends(csrf_guard),
    ) -> Response:
        if not get_service().delete_supplier(supplier_id):
            raise HTTPException(status_code=404, detail="Supplier not found")
        return Response(status_code=204)

    return app


app = create_app()
