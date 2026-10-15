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

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import DictRow, dict_row, scalar_row
from psycopg_pool import ConnectionPool

from ...core.config import Settings

# LangGraph-managed tables; migrations/env.py excludes these from autogenerate/`alembic check`.
CHECKPOINTER_TABLES: frozenset[str] = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)

_setup_done = False
_pool: ConnectionPool[Connection[DictRow]] | None = None
_pool_key: tuple[str, float, int] | None = None
_pool_lock = Lock()
_setup_lock = Lock()
logger = logging.getLogger(__name__)


class _SafePoolLogs(logging.Filter):
    """The driver's reconnect messages contain unreviewed exception text."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = "checkpoint_pool_connection_event service=central-api-rfp"
        record.args = ()
        record.exc_info = None
        record.exc_text = None
        return record.levelno >= logging.WARNING


logging.getLogger("psycopg.pool").addFilter(_SafePoolLogs())


def checkpoint_pool(settings: Settings) -> ConnectionPool[Connection[DictRow]]:
    """One lazy, bounded pool per process; no connection is held across graph execution."""
    global _pool, _pool_key
    key = (_conn_string(settings), settings.database_pool_timeout_seconds, settings.database_connect_timeout_seconds)
    with _pool_lock:
        if _pool is not None:
            if _pool_key != key:
                raise RuntimeError("Checkpoint pool configuration changed before shutdown")
            return _pool
        _pool = ConnectionPool(
            conninfo=key[0], min_size=0, max_size=1, timeout=key[1],
            max_waiting=16, max_idle=60, max_lifetime=300,
            name="trackflow-rfp-checkpoints", open=False,
            kwargs={
                "autocommit": True, "prepare_threshold": 0, "row_factory": dict_row,
                "connect_timeout": key[2], "application_name": "trackflow:rfp-checkpoints",
                "options": (
                    f"-c statement_timeout={settings.database_statement_timeout_ms} "
                    f"-c lock_timeout={settings.database_lock_timeout_ms}"
                ),
            },
        )
        _pool_key = key
        _pool.open()
        logger.info("database_pool_configured service=central-api-rfp min_size=0 max_size=1 timeout_seconds=%s", key[1])
        return _pool


def close_checkpoint_pool() -> None:
    """Release database sessions and pool threads on application shutdown."""
    global _pool, _pool_key, _setup_done
    with _pool_lock:
        if _pool is not None:
            _pool.close()
        _pool = None
        _pool_key = None
        _setup_done = False


def _normalize_conn_string(database_url: str) -> str:
    """Strip only the SQLAlchemy scheme suffix; credentials are opaque."""
    for prefix in ("postgresql+psycopg2://", "postgresql+psycopg://"):
        if database_url.startswith(prefix):
            return "postgresql://" + database_url.removeprefix(prefix)
    return database_url


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
    with saver.conn.connection() as connection, connection.cursor(row_factory=scalar_row) as cursor:
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
    saver = PostgresSaver(checkpoint_pool(settings))
    with _setup_lock:
        if not _setup_done:
            if not _tables_present(saver):
                saver.setup()
            _setup_done = True
    yield saver
