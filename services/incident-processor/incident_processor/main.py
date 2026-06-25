"""FastAPI app for the TrackFlow incident processor."""

from __future__ import annotations

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from trackflow_auth import (
    AuthenticatedPrincipal,
    authenticate_request,
    require_csrf,
    safe_request_validation_exception_handler,
)

from .analysis import analyze_csv_bytes
from .config import get_auth_config, get_cors_origins
from .models import AnalysisResult, IncidentCsvError
from .reporting import build_export_csv


def create_app() -> FastAPI:
    app = FastAPI(title="TrackFlow Incident Processor", version="0.1.0")
    app.add_exception_handler(RequestValidationError, safe_request_validation_exception_handler)
    app.state.latest_incident_analysis = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    # Verifies the Auth 1 access token for incident business routes.
    def current_principal(request: Request) -> AuthenticatedPrincipal:
        return authenticate_request(request, get_auth_config())

    # Enforces CSRF on the file-upload mutation endpoint.
    def csrf_guard(request: Request) -> None:
        require_csrf(request, get_auth_config())

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/incidents/analyze")
    async def analyze_incidents(
        file: UploadFile = File(...),
        _principal: AuthenticatedPrincipal = Depends(current_principal),
        _csrf: None = Depends(csrf_guard),
    ) -> dict[str, object]:
        try:
            payload = await file.read()
            result = analyze_csv_bytes(payload)
        except IncidentCsvError as exc:
            raise HTTPException(status_code=400, detail=exc.to_dict()) from exc

        # Demo-grade storage by design: one in-memory slot, last write wins,
        # cleared on restart, single worker only. Real persistence is deferred
        # to the Central API engagement.
        app.state.latest_incident_analysis = result
        return result.to_dict()

    @app.get("/api/incidents/results/export")
    async def export_latest_analysis(
        _principal: AuthenticatedPrincipal = Depends(current_principal),
    ) -> Response:
        result: AnalysisResult | None = app.state.latest_incident_analysis
        if result is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "NO_ANALYSIS_AVAILABLE",
                    "message": "No incident analysis has been run in this process.",
                },
            )

        return Response(
            content=build_export_csv(result),
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="incident-analysis.csv"'},
        )

    return app


app = create_app()
