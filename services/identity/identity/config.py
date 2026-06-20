"""Runtime configuration for the identity API."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Keeps local Back Office origins explicit for credentialed cookie requests.
DEFAULT_CORS_ORIGINS = ("http://localhost:3000", "http://127.0.0.1:3000")
# Stores the local TinyDB file inside the identity service by default.
DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "identity.json"


# Carries all identity runtime settings after environment parsing.
@dataclass(frozen=True)
class IdentitySettings:
    db_path: Path
    jwt_private_key: str
    jwt_public_key: str
    jwt_algorithm: str
    jwt_issuer: str
    jwt_audience: str
    access_token_expire_minutes: int
    refresh_token_expire_days: int
    cors_origins: list[str]
    cookie_secure: bool
    cookie_samesite: str


# Converts escaped PEM newlines from .env-compatible values.
def _pem_from_env(raw: str) -> str:
    return raw.replace("\\n", "\n").strip()


# Parses bool-like env strings while preserving explicit defaults.
def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# Parses integer env values used for token lifetimes.
def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name, "")
    if not raw.strip():
        return default
    return int(raw)


# Resolves the TinyDB path from env or the service-local default.
def get_db_path() -> Path:
    raw = os.getenv("IDENTITY_DB_PATH", "")
    if not raw.strip():
        return DEFAULT_DB_PATH
    return Path(raw).expanduser()


# Reads the explicit CORS allowlist for credentialed browser calls.
def get_cors_origins() -> list[str]:
    raw = os.getenv("IDENTITY_CORS_ORIGINS", "")
    if not raw.strip():
        return list(DEFAULT_CORS_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


# Builds one settings object from all identity-related env vars.
def get_settings() -> IdentitySettings:
    return IdentitySettings(
        db_path=get_db_path(),
        jwt_private_key=_pem_from_env(os.getenv("IDENTITY_JWT_PRIVATE_KEY", "")),
        jwt_public_key=_pem_from_env(os.getenv("IDENTITY_JWT_PUBLIC_KEY", "")),
        jwt_algorithm=os.getenv("IDENTITY_JWT_ALGORITHM", "RS256").strip() or "RS256",
        jwt_issuer=os.getenv("IDENTITY_JWT_ISSUER", "trackflow-identity").strip() or "trackflow-identity",
        jwt_audience=os.getenv("IDENTITY_JWT_AUDIENCE", "trackflow-backoffice").strip() or "trackflow-backoffice",
        access_token_expire_minutes=_get_int("ACCESS_TOKEN_EXPIRE_MINUTES", 15),
        refresh_token_expire_days=_get_int("REFRESH_TOKEN_EXPIRE_DAYS", 14),
        cors_origins=get_cors_origins(),
        cookie_secure=_get_bool("AUTH_COOKIE_SECURE", False),
        cookie_samesite=os.getenv("AUTH_COOKIE_SAMESITE", "lax").strip().lower() or "lax",
    )
