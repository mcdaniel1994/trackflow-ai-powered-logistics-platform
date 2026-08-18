"""FastAPI application factory and safe service-level failure boundaries."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response
from trackflow_auth import (  # type: ignore[import-untyped]
    safe_request_validation_exception_handler,
    safe_validation_errors,
)

from .core.config import get_settings
from .db.session import get_session
from .domains.agents.router import router as agents_router
from .domains.agents.service import AgentError
from .domains.chat.realtime import router as chat_realtime_router
from .domains.chat.router import router as chat_router
from .domains.chat.service import ChatError
from .domains.chat.streaming import ChatGenerationManager
from .domains.incidents.router import router as incidents_router
from .domains.incidents.service import IncidentError
from .domains.inventory.router import router as inventory_router
from .domains.inventory.schemas import HealthRead
from .domains.inventory.service import InventoryError
from .domains.rag.router import router as rag_router
from .domains.rag.service import RagError
from .domains.realtime.bus import RealtimeBus
from .domains.realtime.router import router as realtime_router
from .domains.reporting.router import router as reporting_router
from .domains.reporting.service import ReportingError
from .domains.rfp.router import router as rfp_router
from .domains.rfp.service import RfpError
from .domains.suppliers.router import router as suppliers_router
from .domains.suppliers.service import SupplierError
from .domains.telemetry.recorder import access_denied_task, dispatch_rejection_task
from .domains.telemetry.router import router as telemetry_router
from .domains.telemetry.service import TelemetryError
from .health import ReadinessFailure, check_readiness, reporting_verification


def _access_denied_reason(exc: StarletteHTTPException) -> str | None:
    """Map only the auth-boundary refusals the verifier actually distinguishes.

    The shared verifier normalizes every token fault to one non-enumerating 401, so no
    finer token reason is observable here without changing it.
    """
    if exc.status_code == 401 and exc.detail == "Not authenticated":
        return "unauthenticated"
    if exc.status_code == 403 and exc.detail == "Password change required":
        return "password_change_required"
    if exc.status_code == 403 and exc.detail == "CSRF token missing or invalid":
        return "csrf"
    return None

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _application_lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Release application-scoped realtime subscriptions during shutdown."""
    yield
    chat_manager = getattr(app.state, "chat_generation_manager", None)
    if isinstance(chat_manager, ChatGenerationManager):
        await chat_manager.close()
    bus = getattr(app.state, "realtime_bus", None)
    if isinstance(bus, RealtimeBus):
        bus.close()


def create_app() -> FastAPI:
    """Build the service app while keeping configuration injectable in later phases."""
    settings = get_settings()
    app = FastAPI(title="TrackFlow Central API", version="0.1.0", lifespan=_application_lifespan)
    app.state.realtime_bus = RealtimeBus()
    app.state.chat_generation_manager = ChatGenerationManager(app.state.realtime_bus)

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
        # A rejected dispatch emits a best-effort diagnostic AFTER the response is sent.
        background = None
        if exc.reject_event is not None:
            background = dispatch_rejection_task(
                warehouse=exc.reject_event.warehouse,
                reason_code=exc.reject_event.reason_code,
                quantity=exc.reject_event.quantity,
            )
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            background=background,
        )

    @app.exception_handler(TelemetryError)
    async def telemetry_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, TelemetryError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ReportingError)
    async def reporting_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, ReportingError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.error_code, "message": exc.detail, "fields": {}}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_with_telemetry(request: Request, exc: Exception) -> Response:
        """Preserve the standard HTTP error response, attaching best-effort denial telemetry."""
        if not isinstance(exc, StarletteHTTPException):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        response = await http_exception_handler(request, exc)
        reason = _access_denied_reason(exc)
        if reason is not None:
            task = access_denied_task(reason=reason)
            if task is not None:
                response.background = task
        return response

    @app.exception_handler(IncidentError)
    async def incident_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, IncidentError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        fields = {exc.field: exc.message} if exc.field else {}
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "fields": fields}},
        )

    @app.exception_handler(SupplierError)
    async def supplier_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, SupplierError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RagError)
    async def rag_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RagError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(AgentError)
    async def agent_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, AgentError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(ChatError)
    async def chat_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, ChatError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RfpError)
    async def rfp_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        if not isinstance(exc, RfpError):
            return JSONResponse(status_code=500, content={"detail": "Internal server error"})
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(SQLAlchemyError)
    async def database_error_handler(_request: Request, exc: Exception) -> JSONResponse:
        """Catch unexpected driver failures while keeping URLs and SQL out of logs."""
        logger.error("unhandled_database_failure error_type=%s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Inventory service temporarily unavailable"})

    @app.get("/health/live")
    def health_live() -> dict[str, str]:
        """Confirm only that the application process can serve requests."""
        return {"status": "alive"}

    def readiness(session: Session) -> JSONResponse | None:
        try:
            check_readiness(session, settings)
        except ReadinessFailure as exc:
            logger.error("readiness_failed check=%s", exc.check)
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        except SQLAlchemyError as exc:
            logger.error("readiness_database_failure error_type=%s", type(exc).__name__)
            return JSONResponse(status_code=503, content={"status": "not_ready"})
        return None

    @app.get("/health/ready", response_model=None)
    def health_ready(session: Annotated[Session, Depends(get_session)]) -> dict[str, str] | JSONResponse:
        """Verify database, compatible schema, and the production runtime role."""
        failure = readiness(session)
        return failure or {"status": "ready"}

    @app.get("/health/reporting", response_model=None)
    def health_reporting(
        session: Annotated[Session, Depends(get_session)],
    ) -> dict[str, object] | JSONResponse:
        """Expose reporting-only verification without affecting core availability."""
        try:
            evidence = reporting_verification(session)
        except ReadinessFailure as exc:
            logger.error("reporting_verification_failed check=%s", exc.check)
            return JSONResponse(
                status_code=503,
                content={"status": "not_verified", "check": exc.check},
            )
        except SQLAlchemyError as exc:
            logger.error("reporting_verification_database_failure error_type=%s", type(exc).__name__)
            return JSONResponse(
                status_code=503,
                content={"status": "not_verified", "check": "reporting_database"},
            )
        return evidence

    @app.get("/health", response_model=HealthRead)
    def health(session: Annotated[Session, Depends(get_session)]) -> HealthRead | JSONResponse:
        """Compatibility alias retaining the original successful response contract."""
        failure = readiness(session)
        if failure is not None:
            return JSONResponse(status_code=503, content={"detail": "Inventory database unavailable"})
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
    app.include_router(suppliers_router)
    app.include_router(telemetry_router)
    app.include_router(reporting_router)
    app.include_router(rag_router)
    app.include_router(agents_router)
    app.include_router(chat_router)
    app.include_router(chat_realtime_router)
    app.include_router(rfp_router)
    app.include_router(realtime_router)
    return app


app = create_app()
