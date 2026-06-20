"""Runtime configuration for the incident processor API."""

from __future__ import annotations

import os

from trackflow_auth import TokenVerifierConfig

DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")


def get_cors_origins() -> list[str]:
    raw = os.getenv("INCIDENT_PROCESSOR_CORS_ORIGINS", "")
    if not raw.strip():
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# Converts escaped PEM newlines from .env-compatible values.
def _pem_from_env(raw: str) -> str:
    return raw.replace("\\n", "\n").strip()


# Builds the public-key verifier config used by protected routes.
def get_auth_config() -> TokenVerifierConfig:
    return TokenVerifierConfig(
        public_key=_pem_from_env(os.getenv("IDENTITY_JWT_PUBLIC_KEY", "")),
        algorithm=os.getenv("IDENTITY_JWT_ALGORITHM", "RS256").strip() or "RS256",
        issuer=os.getenv("IDENTITY_JWT_ISSUER", "trackflow-identity").strip() or "trackflow-identity",
        audience=os.getenv("IDENTITY_JWT_AUDIENCE", "trackflow-backoffice").strip() or "trackflow-backoffice",
    )
