"""Runtime configuration for the incident processor API."""

from __future__ import annotations

import os

DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def get_cors_origins() -> list[str]:
    raw = os.getenv("INCIDENT_PROCESSOR_CORS_ORIGINS", "")
    if not raw.strip():
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]

