"""Bounded, payload-free diagnostics shared by the runtime database pools."""

import logging

from sqlalchemy import Connection, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.pool import PoolProxiedConnection, QueuePool

logger = logging.getLogger(__name__)


class ObservedQueuePool(QueuePool):
    """Report a checkout timeout without logging driver errors, SQL, or credentials."""

    def connect(self) -> PoolProxiedConnection:
        try:
            return super().connect()
        except PoolTimeout:
            logger.error(
                "database_pool_exhausted service=%s size=%s checked_out=%s overflow=%s",
                self.logging_name, self.size(), self.checkedout(), self.overflow(),
            )
            raise


def acquire_session_lock(connection: Connection, key: int) -> bool:
    """Retain a session advisory lock, never the acquisition transaction."""
    try:
        acquired = bool(connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": key}))
        connection.commit()
        return acquired
    except SQLAlchemyError:
        connection.invalidate()
        raise


def session_lock_owner(connection: Connection, key: int) -> int | None:
    """Return the original lock-holding backend, without reconnecting invalidated sessions."""
    if connection.closed or connection.invalidated:
        return None
    try:
        owner = connection.scalar(
            text(
                "SELECT pg_backend_pid() WHERE EXISTS (SELECT 1 FROM pg_locks "
                "WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND granted "
                "AND classid::bigint = :high AND objid::bigint = :low AND objsubid = 1)"
            ),
            {"high": (key >> 32) & 0xFFFFFFFF, "low": key & 0xFFFFFFFF},
        )
        connection.commit()
        return int(owner) if owner is not None else None
    except SQLAlchemyError:
        connection.invalidate()
        raise


def release_session_lock(connection: Connection, key: int) -> None:
    """Never return a possibly locked physical session to the reusable pool."""
    if connection.closed or connection.invalidated:
        return
    try:
        released = connection.scalar(text("SELECT pg_advisory_unlock(:key)"), {"key": key})
        connection.commit()
        if not released:
            connection.invalidate()
    except SQLAlchemyError as exc:
        logger.error("database_lock_cleanup_failed error_type=%s", type(exc).__name__)
        connection.invalidate()
