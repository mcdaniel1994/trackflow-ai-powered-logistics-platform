"""Enforce telemetry retention by pruning rows past each category's window.

Operational rows (default 90 days) and security rows (default 365 days) are deleted
independently. Wire this to a scheduled runner before enabling production telemetry
collection (see docs/runbooks/telemetry-inventory.md).

Usage:
    python -m scripts.prune_telemetry_events
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from central_api.core.config import get_settings
from central_api.db.session import get_engine
from central_api.domains.telemetry.service import TelemetryService

logger = logging.getLogger("central_api.telemetry.prune")


def prune_once() -> dict[str, int]:
    """Delete expired telemetry rows and return the per-category deletion counts."""
    settings = get_settings()
    now = datetime.now(UTC)
    operational_cutoff = now - timedelta(days=settings.telemetry_operational_retention_days)
    security_cutoff = now - timedelta(days=settings.telemetry_security_retention_days)
    with Session(get_engine()) as session:
        deleted = TelemetryService(session).prune(
            operational_cutoff=operational_cutoff,
            security_cutoff=security_cutoff,
        )
    return deleted


def entrypoint() -> None:
    logging.basicConfig(level=logging.INFO)
    deleted = prune_once()
    logger.info(
        "telemetry_prune_complete operational_deleted=%s security_deleted=%s",
        deleted["operational"],
        deleted["security"],
    )


if __name__ == "__main__":
    entrypoint()
