"""Bounded, retry-safe retention for agent traces only."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from central_api.core.config import get_settings
from central_api.db.session import get_engine
from central_api.domains.agents.repository import AgentRepository

logger = logging.getLogger(__name__)
DEFAULT_BATCH_SIZE = 500


def prune_once(*, now: datetime | None = None, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    settings = get_settings()
    cutoff = (now or datetime.now(UTC)) - timedelta(days=settings.agents_trace_retention_days)
    started = time.perf_counter()
    try:
        with Session(get_engine()) as session:
            deleted = AgentRepository(session).delete_before(cutoff, limit=batch_size)
            session.commit()
    except Exception as exc:
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.error(
            "agent_trace_retention outcome=failure cutoff=%s count=0 duration_ms=%s error_type=%s",
            cutoff.isoformat(),
            duration_ms,
            type(exc).__name__,
        )
        raise
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    logger.info(
        "agent_trace_retention outcome=success cutoff=%s count=%s duration_ms=%s",
        cutoff.isoformat(),
        deleted,
        duration_ms,
    )
    return deleted


if __name__ == "__main__":
    prune_once()
