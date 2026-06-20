"""Runtime configuration for the supplier directory API."""

from __future__ import annotations

import os
from pathlib import Path

from trackflow_auth import TokenVerifierConfig

DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "suppliers.json"


def get_db_path() -> Path:
    raw = os.getenv("SUPPLIER_DIRECTORY_DB_PATH", "")
    if not raw.strip():
        return DEFAULT_DB_PATH
    return Path(raw).expanduser()


def get_cors_origins() -> list[str]:
    raw = os.getenv("SUPPLIER_DIRECTORY_CORS_ORIGINS", "")
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
