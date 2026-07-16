"""Fail-closed startup assertions for the reporting worker.

Compose used to gate this worker on two one-shot guard containers via
`service_completed_successfully`. That put the guards on the deploy critical
path: `docker compose up -d` stays attached until such dependencies exit, so a
slow guard was charged against Coolify's command boundary and the deployment was
killed before the worker ever started.

The same conditions are asserted here instead, in the process that actually
consumes them. A failure now restarts one container under `restart: on-failure`
rather than failing the whole deployment, and it can never be satisfied by a
guard that merely *looks* like it passed.

Every rejection carries a fixed reason slug, so a failure names itself.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import DBAPIError

from .prefect_version import GuardFailure, client_version, server_version, verify_compatibility

DEFAULT_TIMEOUT_SECONDS = 60.0
DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10
# A probe must never outlive the overall deadline, so its statement timeout is
# clamped to the remaining budget as well as this ceiling.
MAX_PROBE_SECONDS = 10.0


class StartupGuardFailure(RuntimeError):
    """Startup rejection carrying a fixed reason slug safe to log."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _verify_version_compatibility() -> None:
    """Reject a client newer than its dedicated server.

    Deliberately runs before any I/O: it is static, so a mismatch fails
    immediately rather than after a database retry loop.
    """
    try:
        verify_compatibility(client=client_version(), server=server_version())
    except GuardFailure as failure:
        raise StartupGuardFailure(failure.reason) from None


def guard_database_url() -> URL:
    """Build the guard DSN from discrete parts.

    Never interpolate the password into a URL string: `@`, `:`, `/`, `+` and `=`
    are all legal in a generated password and would silently corrupt it.
    URL.create escapes them correctly.
    """
    password = os.environ.get("PREFECT_GUARD_DB_PASSWORD", "")
    host = os.environ.get("PREFECT_GUARD_DB_HOST", "").strip()
    if not password or not host:
        raise StartupGuardFailure("guard_database_config_missing")
    try:
        port = int(os.environ.get("PREFECT_GUARD_DB_PORT", "5432"))
    except ValueError:
        raise StartupGuardFailure("guard_database_config_invalid") from None
    return URL.create(
        "postgresql+psycopg",
        username=os.environ.get("PREFECT_GUARD_DB_USER", "prefect_guard"),
        password=password,
        host=host,
        port=port,
        database=os.environ.get("PREFECT_GUARD_DB_NAME", "prefect"),
    )


def _probe_prefect_database(url: URL, *, budget_seconds: float) -> str | None:
    """Return a fixed failure reason, or None when the database satisfies the contract.

    Bounded on both sides: connect_timeout caps reaching the server, and
    statement_timeout caps a query that connects but then blocks — without the
    latter, a lock wait could outlast PREFECT_GUARD_TIMEOUT_SECONDS entirely.
    """
    connect_timeout = min(
        int(os.environ.get("DATABASE_CONNECT_TIMEOUT_SECONDS", DEFAULT_CONNECT_TIMEOUT_SECONDS)),
        max(int(budget_seconds), 1),
    )
    statement_timeout_ms = max(int(min(budget_seconds, MAX_PROBE_SECONDS) * 1000), 1000)
    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": connect_timeout,
            "options": f"-c statement_timeout={statement_timeout_ms}",
        },
    )
    try:
        with engine.connect() as connection:
            trgm = connection.execute(
                text("SELECT count(*) FROM pg_extension WHERE extname = 'pg_trgm'")
            ).scalar_one()
            if trgm != 1:
                # Created by the image-baked init file and reapplied by the
                # bootstrap; absent means neither ran against this volume.
                return "pg_trgm_missing"
            flow_run = connection.execute(
                text(
                    "SELECT count(*) FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename = 'flow_run'"
                )
            ).scalar_one()
            if flow_run != 1:
                # A missing state table proves Prefect fell back off PostgreSQL —
                # or is still migrating, which is why the caller retries.
                return "flow_run_table_missing"
    except DBAPIError as error:
        # Distinguish a blocked query from an unreachable server: they point at
        # different causes, and both must stay greppable fixed slugs.
        return "prefect_database_query_timeout" if _is_query_timeout(error) else "prefect_database_unreachable"
    except Exception:
        return "prefect_database_unreachable"
    finally:
        engine.dispose()
    return None


def _is_query_timeout(error: DBAPIError) -> bool:
    """Detect PostgreSQL query_canceled (SQLSTATE 57014) from statement_timeout."""
    sqlstate = getattr(getattr(error, "orig", None), "sqlstate", None)
    return sqlstate == "57014"


def verify_startup_contract(
    *,
    timeout_seconds: float | None = None,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    monotonic: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Assert Prefect is PostgreSQL-backed, migrated, and version-compatible.

    Retries until the deadline: prefect-server reports healthy as soon as its API
    binds, which does not prove its first-boot migration created `flow_run`.
    Raises StartupGuardFailure at the first static rejection or at the deadline;
    the deadline guarantees this can never hang the worker.
    """
    _verify_version_compatibility()

    if timeout_seconds is None:
        timeout_seconds = float(os.environ.get("PREFECT_GUARD_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS))

    url = guard_database_url()
    deadline = monotonic() + timeout_seconds
    while True:
        remaining = deadline - monotonic()
        reason = _probe_prefect_database(url, budget_seconds=max(remaining, 1.0))
        if reason is None:
            return
        if monotonic() >= deadline:
            raise StartupGuardFailure(reason)
        sleep(interval_seconds)
