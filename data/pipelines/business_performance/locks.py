"""Dedicated-connection PostgreSQL advisory lock for report publication."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, text

REPORTING_PIPELINE_LOCK_KEY = 4_306_160_007


@contextmanager
def advisory_lock(engine: Engine, lock_key: int = REPORTING_PIPELINE_LOCK_KEY) -> Iterator[bool]:
    """Hold a session lock on one dedicated connection for the guarded work."""
    with engine.connect() as connection:
        acquired = bool(
            connection.execute(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": lock_key},
            ).scalar_one()
        )
        try:
            yield acquired
        finally:
            if acquired:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:lock_key)"),
                    {"lock_key": lock_key},
                )
