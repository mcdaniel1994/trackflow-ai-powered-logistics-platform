"""Runtime configuration for the supplier directory API."""

from __future__ import annotations

import os
from pathlib import Path

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
