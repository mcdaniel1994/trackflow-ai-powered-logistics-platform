"""Dedicated-connection PostgreSQL advisory lock for report publication."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine

from pipelines.database import acquire_session_lock, release_session_lock

REPORTING_PIPELINE_LOCK_KEY = 4_306_160_007


@contextmanager
def advisory_lock(engine: Engine, lock_key: int = REPORTING_PIPELINE_LOCK_KEY) -> Iterator[bool]:
    """Hold a session lock on one dedicated connection for the guarded work."""
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
        acquired = acquire_session_lock(connection, lock_key)
        try:
            yield acquired
        finally:
            if acquired:
                release_session_lock(connection, lock_key)
