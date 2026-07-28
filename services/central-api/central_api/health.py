"""Non-sensitive liveness and production-readiness checks."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlmodel import Session

from .core.config import Settings
from .domains.reporting.status import WORKER_STALE_AFTER, QueueSignals, derive_queue_state

SERVICE_ROOT = Path(__file__).resolve().parents[1]
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
    "pipeline_run_attempts",
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


def _check_runtime_role(session: Session, settings: Settings) -> None:
    current_user = str(session.scalar(text("SELECT current_user")))
    if settings.app_env.strip().lower() == "production" and current_user != settings.runtime_database_role:
        raise ReadinessFailure("runtime_role")


def _check_reporting_access(session: Session) -> None:
    if not session.scalar(text("SELECT has_schema_privilege(current_user, 'reporting', 'USAGE')")):
        raise ReadinessFailure("reporting_access")
    for table_name in REQUIRED_REPORTING_TABLES:
        if not session.scalar(
            text("SELECT has_table_privilege(current_user, :table_name, 'SELECT,INSERT,UPDATE,DELETE')"),
            {"table_name": f"reporting.{table_name}"},
        ):
            raise ReadinessFailure("reporting_access")


def reporting_verification(session: Session) -> dict[str, object]:
    """Return bounded reporting-only health evidence; never participates in core readiness."""
    _check_reporting_access(session)
    worker = session.execute(
        text(
            "SELECT heartbeat_at, last_progress_at, orchestrator_healthy "
            "FROM reporting.worker_heartbeats WHERE worker_name = 'reporting'"
        )
    ).mappings().one_or_none()
    now = session.scalar(text("SELECT now()"))
    if not isinstance(now, datetime):
        now = datetime.now(UTC)

    running = session.execute(
        text(
            "SELECT current_stage, stage_started_at FROM reporting.pipeline_runs "
            "WHERE pipeline_name = 'business_performance' AND status = 'running' "
            "ORDER BY started_at LIMIT 1"
        )
    ).mappings().one_or_none()
    latest = session.execute(
        text(
            "SELECT status, error_code, attempt FROM reporting.pipeline_runs "
            "WHERE pipeline_name = 'business_performance' "
            "ORDER BY requested_at DESC, id DESC LIMIT 1"
        )
    ).mappings().one_or_none()
    latest_successful = session.execute(
        text(
            "SELECT source_watermark, finished_at FROM reporting.pipeline_runs "
            "WHERE pipeline_name = 'business_performance' AND status = 'succeeded' "
            "ORDER BY finished_at DESC NULLS LAST, requested_at DESC LIMIT 1"
        )
    ).mappings().one_or_none()
    heartbeat_at = worker["heartbeat_at"] if worker is not None else None
    last_progress_at = worker["last_progress_at"] if worker is not None else None
    orchestrator_healthy = worker["orchestrator_healthy"] if worker is not None else None
    queue_state = derive_queue_state(
        QueueSignals(
            heartbeat_at=heartbeat_at,
            last_progress_at=last_progress_at,
            orchestrator_healthy=orchestrator_healthy,
            running_stage=running["current_stage"] if running is not None else None,
            stage_started_at=running["stage_started_at"] if running is not None else None,
            latest_status=latest["status"] if latest is not None else None,
            queued_count=int(
                session.scalar(
                    text(
                        "SELECT count(*) FROM reporting.pipeline_runs "
                        "WHERE pipeline_name = 'business_performance' "
                        "AND status IN ('requested', 'retryable')"
                    )
                )
                or 0
            ),
        ),
        now=now,
    )
    heartbeat_age_seconds = (
        max(0, int((now - heartbeat_at).total_seconds()))
        if isinstance(heartbeat_at, datetime)
        else None
    )
    return {
        "status": "verified" if queue_state not in {"unavailable", "stuck"} else "degraded",
        "queue_state": queue_state,
        "worker_heartbeat_age_seconds": heartbeat_age_seconds,
        "worker_stale": heartbeat_age_seconds is None
        or heartbeat_age_seconds > int(WORKER_STALE_AFTER.total_seconds()),
        "orchestrator_healthy": orchestrator_healthy,
        "last_successful_cutoff_at": latest_successful["source_watermark"]
        if latest_successful is not None
        else None,
        "last_published_at": latest_successful["finished_at"] if latest_successful is not None else None,
        "stale": queue_state in {"unavailable", "stuck"},
        "latest_error_code": latest["error_code"] if latest is not None else None,
        "attempt_count": int(latest["attempt"]) if latest is not None else 0,
        "reporting_access": "verified",
    }


def check_readiness(session: Session, settings: Settings) -> None:
    """Verify only core dependencies whose failure makes the application unsafe."""
    _check_database(session)
    _check_schema_compatibility(session)
    _check_runtime_role(session, settings)
