"""Explicit transient-connectivity classification for reporting SQL operations."""

from __future__ import annotations

import socket
import time
from collections.abc import Callable
from typing import TypeVar

from sqlalchemy.exc import DBAPIError, SQLAlchemyError

T = TypeVar("T")

_TRANSIENT_SQLSTATES = {
    "57P01",  # administrator shutdown
    "57P02",  # crash shutdown
    "57P03",  # cannot connect now
}
_TRANSIENT_TEXT = (
    "connection refused",
    "connection reset",
    "connection closed unexpectedly",
    "server closed the connection unexpectedly",
    "connection is closed",
    "connect timeout",
    "connection timeout",
    "timeout expired",
    "temporarily unavailable",
    "database system is starting up",
    "could not translate host name",
    "temporary failure in name resolution",
    "name or service not known",
)


def _chain(exc: BaseException) -> list[BaseException]:
    values: list[BaseException] = []
    current: BaseException | None = exc
    while current is not None and current not in values:
        values.append(current)
        current = current.__cause__ or current.__context__
    return values


def is_transient_connectivity_failure(exc: BaseException) -> bool:
    """Return true only for the specification's connectivity allowlist."""
    for candidate in _chain(exc):
        if isinstance(
            candidate,
            (
                ConnectionRefusedError,
                ConnectionResetError,
                ConnectionAbortedError,
                socket.gaierror,
                TimeoutError,
            ),
        ):
            return True
        if isinstance(candidate, DBAPIError):
            sqlstate = getattr(candidate.orig, "sqlstate", None) or getattr(
                candidate.orig,
                "pgcode",
                None,
            )
            if isinstance(sqlstate, str):
                return sqlstate.startswith("08") or sqlstate in _TRANSIENT_SQLSTATES
        if isinstance(candidate, (SQLAlchemyError, OSError)):
            normalized = str(candidate).lower()
            if any(fragment in normalized for fragment in _TRANSIENT_TEXT):
                return True
    return False


def run_with_transient_retries(
    operation: Callable[[], T],
    *,
    delays: tuple[float, ...] = (0.25, 0.5),
    sleeper: Callable[[float], None] = time.sleep,
) -> T:
    """Retry only classified connectivity failures; propagate everything else."""
    for attempt in range(len(delays) + 1):
        try:
            return operation()
        except (SQLAlchemyError, OSError, TimeoutError) as exc:
            if not is_transient_connectivity_failure(exc) or attempt == len(delays):
                raise
            sleeper(delays[attempt])
    raise AssertionError("unreachable")
