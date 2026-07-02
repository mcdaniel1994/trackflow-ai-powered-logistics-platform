"""FastAPI application factory and safe service-level failure boundaries."""

import logging
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from trackflow_auth import (  # type: ignore[import-untyped]
    safe_request_validation_exception_handler,
    safe_validation_errors,
)

from .core.config import get_settings
from .db.session import get_session
from .domains.incidents.router import router as incidents_router
from .domains.incidents.service import IncidentError
from .domains.inventory.router import router as inventory_router
from .domains.inventory.schemas import HealthRead
from .domains.inventory.service import InventoryError

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Build the service app while keeping configuration injectable in later phases."""
    settings = get_settings()
    app = FastAPI(title="TrackFlow Central API", version="0.1.0")
    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RequestValidationError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        if request.url.path.startswith("/api/incidents"):
            fields: dict[str, str] = {}
            for error in safe_validation_errors(exc.errors()):
                location = error.get("loc", [])
                field = str(location[-1]) if isinstance(location, list) and location else "request"
                fields[field] = str(error.get("msg", "Invalid value."))
            return JSONResponse(
                status_code=400,
                content={
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Request validation failed.",
                        "fields": fields,
                    }
                },
            )
        return cast(JSONResponse, await safe_request_validation_exception_handler(request, exc))

    # The explicit allowlist supports cookie auth without opening credentialed CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    @app.exception_handler(InventoryError)
    async def inventory_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Translate typed domain failures without exposing internal exceptions."""
        if not isinstance(exc, InventoryError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(IncidentError)
    async def incident_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, IncidentError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        fields = {exc.field: exc.message} if exc.field else {}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "fields": fields}},
        )

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Catch unexpected driver failures while keeping URLs and SQL out of logs."""
        logger.error("unhandled_database_failure error_type=%s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Inventory service temporarily unavailable"})

    @app.get("/health", response_model=HealthRead)
    def health(session: Annotated[Session, Depends(get_session)]) -> HealthRead | JSONResponse:
        """Confirm database readiness without returning connection details."""
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.error("health_database_failure error_type=%s", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"detail": "Inventory database unavailable"},
            )
        return HealthRead(status="ok", database="ok")

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_central_api_failure error_type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "Something went wrong. Please try again."}},
        )

    app.include_router(inventory_router)
    app.include_router(incidents_router)
    return app


app = create_app()
