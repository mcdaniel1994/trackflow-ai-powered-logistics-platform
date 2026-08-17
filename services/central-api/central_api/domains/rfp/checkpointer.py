"""Durable LangGraph checkpointer for the RFP human-approval graph (Engagement 9, Phase 3).

The approval graph pauses on a native ``interrupt()`` and must resume from the exact interruption in a
later request, so its state has to outlive the process. We use ``langgraph-checkpoint-postgres``
against the Central API database. Its tables (``checkpoints`` etc.) are managed by ``setup()`` — not
Alembic — and are excluded from ``alembic check`` in ``migrations/env.py``. Provider keys never enter
checkpointed state (they are bound via closure in the graph).

Production runs the app as a least-privilege runtime role that has CRUD but **no ``CREATE``** on the
schema, so ``setup()`` (a ``CREATE TABLE``) cannot run at request time. ``provision_checkpointer_tables``
is called once by the production migration (which connects as the DDL-capable migration role) so the
tables exist before the runtime role needs them; the migration's runtime-grant step then covers them
like any other table. The request-time path only runs ``setup()`` when the tables are absent — i.e. in
local/dev/test, where the connecting role owns the schema.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import scalar_row

from ...core.config import Settings

# LangGraph-managed tables; migrations/env.py excludes these from autogenerate/`alembic check`.
CHECKPOINTER_TABLES: frozenset[str] = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)

_setup_done = False


def _normalize_conn_string(database_url: str) -> str:
    """psycopg3 connection string: drop the SQLAlchemy ``+psycopg2`` driver suffix."""
    return database_url.replace("+psycopg2", "", 1)


def _conn_string(settings: Settings) -> str:
    return _normalize_conn_string(settings.database_url)


def provision_checkpointer_tables(database_url: str) -> None:
    """Create the LangGraph checkpointer tables with a DDL-capable connection.

    Called once by the production migration (migration role, which has ``CREATE``) so the least-privilege
    runtime role never has to issue DDL at request time. Idempotent — LangGraph records applied schema
    migrations in ``checkpoint_migrations`` and re-runs are no-ops.
    """
    with PostgresSaver.from_conn_string(_normalize_conn_string(database_url)) as saver:
        saver.setup()


def _tables_present(saver: Any) -> bool:
    """True when the checkpointer schema already exists (e.g. provisioned by the migration role)."""
    with saver.conn.cursor(row_factory=scalar_row) as cursor:
        cursor.execute("SELECT to_regclass('public.checkpoint_migrations') IS NOT NULL")
        return bool(cursor.fetchone())


@contextmanager
def approval_checkpointer(settings: Settings) -> Iterator[Any]:
    """Yield a live PostgresSaver, provisioning its schema once per process only when absent.

    In production the tables are pre-created by ``provision_checkpointer_tables`` (migration role), so the
    runtime role — which lacks ``CREATE`` — skips ``setup()`` and never issues DDL. Elsewhere the tables
    are absent on first use and ``setup()`` creates them under a schema-owning role.
    """
    global _setup_done
    with PostgresSaver.from_conn_string(_conn_string(settings)) as saver:
        if not _setup_done:
            if not _tables_present(saver):
                saver.setup()
            _setup_done = True
        yield saver
