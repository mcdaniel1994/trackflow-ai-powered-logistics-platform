"""Bounded seven-day cleanup for unresolved agent memory proposals."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session

from central_api.db.session import get_engine
from central_api.domains.agents.memory_repository import AgentMemoryRepository

PENDING_PROPOSAL_RETENTION_DAYS = 7
DEFAULT_BATCH_SIZE = 500


def prune_once(*, now: datetime | None = None, batch_size: int = DEFAULT_BATCH_SIZE) -> int:
    if batch_size < 1 or batch_size > 5_000:
        raise ValueError("batch_size must be between 1 and 5000")
    cutoff = (now or datetime.now(UTC)) - timedelta(days=PENDING_PROPOSAL_RETENTION_DAYS)
    with Session(get_engine()) as session:
        deleted = AgentMemoryRepository(session).delete_expired_pending(cutoff, limit=batch_size)
        session.commit()
        return deleted


if __name__ == "__main__":
    print(f"Deleted {prune_once()} expired pending memory proposals.")
