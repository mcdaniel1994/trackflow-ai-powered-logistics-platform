"""Prune authoritative business-event rows outside the 26-week retention window.

The weekly reporting table remains durable. Only source occurrence rows older than the
configured cutoff are removed; technical telemetry retention is managed separately.

Usage:
    python -m scripts.prune_business_events
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, time, timedelta

from process.business_performance import iso_week_start
from sqlalchemy import text
from sqlmodel import Session

from central_api.core.config import get_settings
from central_api.db.session import get_engine

logger = logging.getLogger("central_api.business_events.prune")


def retention_cutoff(now: datetime, weeks: int) -> datetime:
    """Return the Monday UTC boundary preceding the retained ISO-week window."""
    if weeks <= 0:
        raise ValueError("business-event retention weeks must be positive")
    return datetime.combine(iso_week_start(now) - timedelta(weeks=weeks), time.min, tzinfo=UTC)


def prune_once(*, now: datetime | None = None) -> dict[str, int]:
    settings = get_settings()
    cutoff = retention_cutoff(now or datetime.now(UTC), settings.business_event_retention_weeks)
    with Session(get_engine()) as session:
        discrepancies = session.scalar(
            text(
                "WITH deleted AS (DELETE FROM inventory_discrepancies "
                "WHERE detected_at < :cutoff RETURNING 1) SELECT count(*) FROM deleted"
            ),
            {"cutoff": cutoff},
        )
        stockouts = session.scalar(
            text(
                "WITH deleted AS (DELETE FROM stockout_events "
                "WHERE occurred_at < :cutoff RETURNING 1) SELECT count(*) FROM deleted"
            ),
            {"cutoff": cutoff},
        )
        session.commit()
    return {
        "inventory_discrepancies": int(discrepancies or 0),
        "stockout_events": int(stockouts or 0),
    }


def entrypoint() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    deleted = prune_once()
    logger.info(
        "business_event_prune_complete inventory_discrepancies_deleted=%s stockout_events_deleted=%s",
        deleted["inventory_discrepancies"],
        deleted["stockout_events"],
    )


if __name__ == "__main__":
    entrypoint()
