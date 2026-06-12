"""FastAPI app for the TrackFlow incident processor."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .analysis import analyze_csv_bytes
from .config import get_cors_origins
from .models import AnalysisResult, IncidentCsvError
from .reporting import build_export_csv


def create_app() -> FastAPI:
    app = FastAPI(title="TrackFlow Incident Processor", version="0.1.0")
    app.state.latest_incident_analysis = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/incidents/analyze")
    async def analyze_incidents(file: UploadFile = File(...)) -> dict[str, object]:
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
    async def export_latest_analysis() -> Response:
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

