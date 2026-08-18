"""Bounded 90-day retention for owner-scoped chat history."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from central_api.db.session import get_engine
from central_api.domains.chat.repository import ChatRepository

logger = logging.getLogger(__name__)
CHAT_HISTORY_RETENTION_DAYS = 90
DEFAULT_BATCH_SIZE = 500


def prune_once(*, now: datetime | None = None, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    if batch_size < 1 or batch_size > 5_000:
        raise ValueError("batch_size must be between 1 and 5000")
    cutoff = (now or datetime.now(UTC)) - timedelta(days=CHAT_HISTORY_RETENTION_DAYS)
    started = time.perf_counter()
    try:
        with Session(get_engine()) as session:
            deleted = ChatRepository(session).delete_expired_sessions(cutoff, limit=batch_size)
            session.commit()
    except Exception as exc:
        duration_ms = max(0, int((time.perf_counter() - started) * 1000))
        logger.error(
            "chat_history_retention outcome=failure cutoff=%s count=0 duration_ms=%s error_type=%s",
            cutoff.isoformat(),
            duration_ms,
            type(exc).__name__,
        )
        raise
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    logger.info(
        "chat_history_retention outcome=success cutoff=%s count=%s duration_ms=%s",
        cutoff.isoformat(),
        deleted,
        duration_ms,
    )
    return deleted


if __name__ == "__main__":
    prune_once()
