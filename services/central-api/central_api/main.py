"""FastAPI application factory for the TrackFlow Central API."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings


def create_app() -> FastAPI:
    """Build the service app while keeping configuration injectable in later phases."""
    settings = get_settings()
    app = FastAPI(title="TrackFlow Central API", version="0.1.0")

    # The explicit allowlist supports cookie auth without opening credentialed CORS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
    )

    return app


app = create_app()
