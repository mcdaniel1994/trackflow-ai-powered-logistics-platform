"""Prove the reporting worker cleared its Prefect startup guard after a deploy.

Compose no longer gates reporting-worker on the one-shot Prefect guards, because
`up -d` blocks until such dependencies exit and that put them on Coolify's
command boundary. The worker enforces those conditions itself at startup and
exits non-zero when they fail, so a live, healthy worker heartbeat is the
observable proof that the guards passed.

This replaces a hard-coded `PREFECT_GUARD_RESULT=passed` in the deploy workflow,
which asserted the old Compose ordering rather than measuring anything.

A freshness window alone is not sufficient proof. The *previous* worker
heartbeats until the moment it is replaced, so a heartbeat written seconds before
deployment would still look recent and would pass while the new worker's startup
guard was in fact rejecting the release. Verification therefore requires a
heartbeat strictly at or after a boundary recorded once Coolify returned: the old
container cannot write one after Compose replaced it, so only the new worker can
satisfy it.
"""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import create_engine, text

DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_INTERVAL_SECONDS = 15.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10
DEFAULT_STATEMENT_TIMEOUT_MS = 15_000


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("reporting_startup=failed reason=database_url_missing")
    if url.startswith("postgresql+psycopg2://"):
        url = url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return url


def _verification_boundary() -> datetime:
    """The UTC instant after which only the new worker can have heartbeated."""
    raw = os.environ.get("REPORTING_STARTUP_MIN_HEARTBEAT_AT", "").strip()
    if not raw:
        raise SystemExit("reporting_startup=failed reason=verification_boundary_missing")
    try:
        boundary = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise SystemExit("reporting_startup=failed reason=verification_boundary_invalid") from None
    return boundary if boundary.tzinfo else boundary.replace(tzinfo=UTC)


def evaluate_heartbeat(
    worker: Mapping[str, Any] | None,
    *,
    boundary: datetime,
) -> str | None:
    """Return a fixed failure reason, or None when the new worker proved itself."""
    if worker is None or worker["heartbeat_at"] is None:
        # The worker never reached its poll loop: its startup guard rejected the
        # deployment, or it never started at all.
        return "worker_heartbeat_absent"
    if worker["heartbeat_at"] < boundary:
        # Recent is not enough — this predates the deployment, so it is the
        # previous worker's heartbeat and proves nothing about the new one.
        return "worker_heartbeat_predates_deployment"
    if worker["orchestrator_healthy"] is not True:
        return "orchestrator_unhealthy"
    return None


def _read_heartbeat(engine: Any) -> Mapping[str, Any] | None:
    with engine.connect() as connection:
        row = (
            connection.execute(
                text(
                    "SELECT heartbeat_at, orchestrator_healthy FROM reporting.worker_heartbeats "
                    "WHERE worker_name = 'reporting'"
                )
            )
            .mappings()
            .one_or_none()
        )
    return None if row is None else dict(row)


def verify(
    *,
    boundary: datetime,
    timeout_seconds: float,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> str | None:
    """Poll until the new worker heartbeats past the boundary, or the deadline."""
    connect_timeout = int(os.environ.get("DATABASE_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT_SECONDS))
    statement_timeout = int(os.environ.get("DATABASE_STATEMENT_TIMEOUT_MS", DEFAULT_STATEMENT_TIMEOUT_MS))
    # Bounded on both sides so this workflow container cannot hang against Supabase.
    engine = create_engine(
        _database_url(),
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": connect_timeout,
            "options": f"-c statement_timeout={statement_timeout}",
        },
    )
    deadline = monotonic() + timeout_seconds
    try:
        while True:
            try:
                reason = evaluate_heartbeat(_read_heartbeat(engine), boundary=boundary)
            except Exception:
                reason = "reporting_database_unreachable"
            if reason is None:
                return None
            if monotonic() >= deadline:
                return reason
            sleep(interval_seconds)
    finally:
        engine.dispose()


def main() -> None:
    boundary = _verification_boundary()
    timeout = float(os.environ.get("REPORTING_STARTUP_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))
    reason = verify(boundary=boundary, timeout_seconds=timeout)
    if reason is not None:
        print(f"reporting_startup=failed reason={reason} boundary={boundary.isoformat()}")
        sys.exit(1)
    print(f"reporting_startup=verified orchestrator_healthy=true boundary={boundary.isoformat()}")


if __name__ == "__main__":
    main()
