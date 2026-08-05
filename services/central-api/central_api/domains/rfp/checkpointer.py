"""Durable LangGraph checkpointer for the RFP human-approval graph (Engagement 9, Phase 3).

The approval graph pauses on a native ``interrupt()`` and must resume from the exact interruption in a
later request, so its state has to outlive the process. We use ``langgraph-checkpoint-postgres``
against the Central API database. Its tables (``checkpoints`` etc.) are managed by ``setup()`` — not
Alembic — and are excluded from ``alembic check`` in ``migrations/env.py``. Provider keys never enter
checkpointed state (they are bound via closure in the graph).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver

from ...core.config import Settings

# LangGraph-managed tables; migrations/env.py excludes these from autogenerate/`alembic check`.
CHECKPOINTER_TABLES: frozenset[str] = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)

_setup_done = False


def _conn_string(settings: Settings) -> str:
    """psycopg3 connection string: drop the SQLAlchemy ``+psycopg2`` driver suffix."""
    return settings.database_url.replace("+psycopg2", "", 1)


@contextmanager
def approval_checkpointer(settings: Settings) -> Iterator[Any]:
    """Yield a live PostgresSaver, running its idempotent one-time schema setup once per process."""
    global _setup_done
    with PostgresSaver.from_conn_string(_conn_string(settings)) as saver:
        if not _setup_done:
            saver.setup()
            _setup_done = True
        yield saver
