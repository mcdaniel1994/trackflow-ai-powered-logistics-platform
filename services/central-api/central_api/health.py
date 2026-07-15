"""Non-sensitive liveness and production-readiness checks."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlmodel import Session

from .core.config import Settings

SERVICE_ROOT = Path(__file__).resolve().parents[1]
WORKER_STALE_SECONDS = 30
REQUIRED_SKU_COLUMNS = {
    "id",
    "name",
    "sku",
    "client_id",
    "min_stock_threshold",
    "category",
    "warehouse",
}
REQUIRED_REPORTING_TABLES = {
    "weekly_warehouse_client_performance",
    "pipeline_runs",
    "incomplete_weeks",
    "source_ledger_state",
    "worker_heartbeats",
}
_REVISION = re.compile(r"^[0-9]{8}_[0-9]{4}$")


class ReadinessFailure(RuntimeError):
    """Fixed check identifier suitable for safe operational logging."""

    def __init__(self, check: str) -> None:
        super().__init__("service is not ready")
        self.check = check


@lru_cache
def image_schema_head() -> str:
    config = Config(str(SERVICE_ROOT / "alembic.ini"))
    head = ScriptDirectory.from_config(config).get_current_head()
    if not head or not _REVISION.fullmatch(head):
        raise ReadinessFailure("image_schema")
    return head


def _check_database(session: Session) -> None:
    if session.scalar(text("SELECT 1")) != 1:
        raise ReadinessFailure("database")


def _check_schema_compatibility(session: Session) -> None:
    revision = session.scalar(text("SELECT version_num FROM public.alembic_version"))
    if not isinstance(revision, str) or not _REVISION.fullmatch(revision):
        raise ReadinessFailure("schema_revision")
    # TrackFlow revision IDs are deliberately sortable. A newer database is
    # accepted for expand/contract image rollback; an older database is not.
    if revision < image_schema_head():
        raise ReadinessFailure("schema_revision")

    columns = {
        str(value)
        for value in session.execute(
            text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = 'skus'"
            )
        ).scalars()
    }
    if not REQUIRED_SKU_COLUMNS.issubset(columns):
        raise ReadinessFailure("inventory_schema")


def _check_runtime_reporting_access(session: Session, settings: Settings) -> None:
    current_user = str(session.scalar(text("SELECT current_user")))
    if settings.app_env.strip().lower() == "production" and current_user != settings.runtime_database_role:
        raise ReadinessFailure("runtime_role")
    if not session.scalar(text("SELECT has_schema_privilege(current_user, 'reporting', 'USAGE')")):
        raise ReadinessFailure("reporting_access")
    for table_name in REQUIRED_REPORTING_TABLES:
        if not session.scalar(
            text("SELECT has_table_privilege(current_user, :table_name, 'SELECT,INSERT,UPDATE,DELETE')"),
            {"table_name": f"reporting.{table_name}"},
        ):
            raise ReadinessFailure("reporting_access")


def _check_reporting_worker(session: Session) -> None:
    healthy = session.scalar(
        text(
            "SELECT heartbeat_at >= now() - make_interval(secs => :stale_seconds) "
            "FROM reporting.worker_heartbeats WHERE worker_name = 'reporting'"
        ),
        {"stale_seconds": WORKER_STALE_SECONDS},
    )
    if healthy is not True:
        raise ReadinessFailure("reporting_worker")


def check_readiness(session: Session, settings: Settings) -> None:
    """Raise a fixed check identifier on the first unmet readiness requirement."""
    _check_database(session)
    _check_schema_compatibility(session)
    _check_runtime_reporting_access(session, settings)
    _check_reporting_worker(session)
