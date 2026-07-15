"""PostgreSQL-backed queue transitions for business-performance pipeline runs."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import Connection, Engine, RowMapping, create_engine, text
from sqlalchemy.exc import IntegrityError

from process.business_performance import TransformError, iso_week_start, recomputable_weeks, validate_requested_week

PIPELINE_NAME: Final = "business_performance"
PIPELINE_VERSION: Final = "engagement-6-phase-5"
REPORTING_WORKER_NAME: Final = "reporting"
DEFAULT_RECOMPUTE_WEEKS: Final = 3
DEFAULT_LEASE_SECONDS: Final = 600
DEFAULT_MAX_ATTEMPTS: Final = 5
DEFAULT_BACKOFF_SECONDS: Final = 60

TriggerType = Literal["scheduled", "manual", "cli"]
ErrorCode = Literal[
    "EXTRACT_FAILED",
    "VALIDATE_FAILED",
    "LOAD_FAILED",
    "DB_UNAVAILABLE",
    "LOCK_UNAVAILABLE",
    "STALE_ABANDONED",
    "MAX_ATTEMPTS_EXCEEDED",
]

_SAFE_ERROR_SUMMARIES: Final[dict[str, str]] = {
    "EXTRACT_FAILED": "Source extraction failed",
    "VALIDATE_FAILED": "Source validation failed",
    "LOAD_FAILED": "Report publication failed",
    "DB_UNAVAILABLE": "Reporting database unavailable",
    "LOCK_UNAVAILABLE": "Reporting pipeline is already locked",
    "STALE_ABANDONED": "Worker lease expired",
    "MAX_ATTEMPTS_EXCEEDED": "Maximum attempts exceeded",
}


class QueueConfigurationError(RuntimeError):
    """Raised when runtime queue configuration is absent or unsafe."""


class LeaseLostError(RuntimeError):
    """Raised when a reclaimed worker attempts another state change or publication."""


class QueueValidationError(ValueError):
    """Raised when persisted request parameters cannot form a trustworthy run."""


@dataclass(frozen=True)
class RunClaim:
    run_id: UUID
    claim_token: UUID
    trigger_type: TriggerType
    requested_week_start: date | None
    target_weeks: tuple[date, ...]
    attempt: int


@dataclass(frozen=True)
class RunMetrics:
    rows_extracted: int
    rows_transformed: int
    rows_loaded: int
    source_watermark: datetime | None = None


def utc_now() -> datetime:
    return datetime.now(UTC)


def record_worker_heartbeat(engine: Engine, *, now: datetime | None = None) -> None:
    """Upsert the singleton worker heartbeat without storing host or process identifiers."""
    heartbeat_at = now or utc_now()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.worker_heartbeats (worker_name, heartbeat_at) "
                "VALUES (:worker_name, :heartbeat_at) "
                "ON CONFLICT (worker_name) DO UPDATE SET heartbeat_at = EXCLUDED.heartbeat_at"
            ),
            {"worker_name": REPORTING_WORKER_NAME, "heartbeat_at": heartbeat_at},
        )


def engine_from_environment() -> Engine:
    """Create a psycopg 3 engine without coupling data code to Central API settings."""
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise QueueConfigurationError("DATABASE_URL is required")
    if database_url.startswith("postgresql+psycopg2://"):
        database_url = database_url.replace("postgresql+psycopg2://", "postgresql+psycopg://", 1)
    return create_engine(database_url, pool_pre_ping=True)


def _monday(value: date) -> date:
    if isinstance(value, datetime) or value.isoweekday() != 1:
        raise QueueValidationError("requested_week_start must be an ISO Monday")
    return value


def _row_uuid(row: RowMapping, key: str) -> UUID:
    value = row[key]
    return value if isinstance(value, UUID) else UUID(str(value))


def _request_id(result_row: RowMapping | None) -> UUID | None:
    return None if result_row is None else _row_uuid(result_row, "id")


def enqueue_scheduled(
    engine: Engine,
    business_date: date,
    *,
    now: datetime | None = None,
) -> UUID | None:
    """Insert exactly one scheduled request per Dallas business date."""
    requested_at = now or utc_now()
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "INSERT INTO reporting.pipeline_runs "
                "(pipeline_name, trigger_type, requested_by, scheduled_business_date, requested_at, status) "
                "VALUES (:pipeline_name, 'scheduled', 'system', :business_date, :requested_at, 'requested') "
                "ON CONFLICT (pipeline_name, scheduled_business_date) "
                "WHERE trigger_type = 'scheduled' DO NOTHING RETURNING id"
            ),
            {
                "pipeline_name": PIPELINE_NAME,
                "business_date": business_date,
                "requested_at": requested_at,
            },
        ).mappings().one_or_none()
    return _request_id(row)


def enqueue_manual(
    engine: Engine,
    *,
    requested_by: str,
    requested_week_start: date | None = None,
    force_refresh: bool = False,
    now: datetime | None = None,
) -> UUID:
    """Persist a manual request, coalescing only identical pending non-forced work."""
    if not requested_by.strip():
        raise QueueValidationError("requested_by is required")
    week = _monday(requested_week_start) if requested_week_start is not None else None
    nonce = uuid4() if force_refresh else None
    requested_at = now or utc_now()
    with engine.begin() as connection:
        if week is not None:
            reset_at = connection.execute(
                text("SELECT last_reset_at FROM reporting.source_ledger_state WHERE id = 1")
            ).scalar_one_or_none()
            try:
                validate_requested_week(week, cast(datetime | None, reset_at))
            except TransformError as exc:
                raise QueueValidationError(str(exc)) from exc
        row = connection.execute(
            text(
                "INSERT INTO reporting.pipeline_runs "
                "(pipeline_name, trigger_type, requested_by, requested_week_start, requested_at, "
                " status, cache_nonce) "
                "VALUES (:pipeline_name, 'manual', :requested_by, :week, :requested_at, 'requested', :nonce) "
                "ON CONFLICT (pipeline_name, COALESCE(requested_week_start, DATE '0001-01-01')) "
                "WHERE status = 'requested' AND trigger_type = 'manual' AND cache_nonce IS NULL "
                "DO NOTHING RETURNING id"
            ),
            {
                "pipeline_name": PIPELINE_NAME,
                "requested_by": requested_by,
                "week": week,
                "requested_at": requested_at,
                "nonce": nonce,
            },
        ).mappings().one_or_none()
        if row is not None:
            return _row_uuid(row, "id")
        # The partial unique index is the authority for coalescing; selecting only
        # after its conflict path avoids a read-then-insert race between API workers.
        existing = connection.execute(
            text(
                "SELECT id FROM reporting.pipeline_runs "
                "WHERE pipeline_name = :pipeline_name AND trigger_type = 'manual' "
                "AND status = 'requested' AND cache_nonce IS NULL "
                "AND requested_week_start IS NOT DISTINCT FROM :week"
            ),
            {"pipeline_name": PIPELINE_NAME, "week": week},
        ).mappings().one()
        return _row_uuid(existing, "id")


def enqueue_cli(
    engine: Engine,
    *,
    requested_week_start: date | None = None,
    now: datetime | None = None,
) -> UUID:
    week = _monday(requested_week_start) if requested_week_start is not None else None
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "INSERT INTO reporting.pipeline_runs "
                "(pipeline_name, trigger_type, requested_by, requested_week_start, requested_at, status) "
                "VALUES (:pipeline_name, 'cli', 'cli', :week, :requested_at, 'requested') RETURNING id"
            ),
            {"pipeline_name": PIPELINE_NAME, "week": week, "requested_at": now or utc_now()},
        ).mappings().one()
    return _row_uuid(row, "id")


def _target_weeks(
    requested_week_start: date | None,
    *,
    now: datetime,
    last_reset_at: datetime | None,
    recompute_weeks: int,
) -> tuple[date, ...]:
    if requested_week_start is not None:
        try:
            return (validate_requested_week(requested_week_start, last_reset_at),)
        except TransformError as exc:
            raise QueueValidationError(str(exc)) from exc
    current_week = iso_week_start(now)
    candidates = tuple(current_week - timedelta(weeks=offset) for offset in reversed(range(recompute_weeks)))
    return recomputable_weeks(candidates, last_reset_at)


def claim_next(
    engine: Engine,
    *,
    now: datetime | None = None,
    pipeline_version: str = PIPELINE_VERSION,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
    recompute_weeks: int = DEFAULT_RECOMPUTE_WEEKS,
) -> RunClaim | None:
    """Atomically claim the oldest eligible row and persist its resolved target window."""
    claimed_at = now or utc_now()
    token = uuid4()
    try:
        with engine.begin() as connection:
            row = connection.execute(
                text(
                    "UPDATE reporting.pipeline_runs AS run SET "
                    "status = 'running', started_at = :now, finished_at = NULL, attempt = attempt + 1, "
                    "pipeline_version = :version, claim_token = :token, heartbeat_at = :now, "
                    "lease_expires_at = :lease_expires_at, next_attempt_at = NULL, "
                    "error_code = NULL, error_summary = NULL "
                    "WHERE run.id = (SELECT id FROM reporting.pipeline_runs "
                    "WHERE pipeline_name = :pipeline_name "
                    "AND (status = 'requested' OR (status = 'retryable' AND next_attempt_at <= :now)) "
                    "ORDER BY requested_at LIMIT 1 FOR UPDATE SKIP LOCKED) "
                    "RETURNING run.id, run.claim_token, run.trigger_type, run.requested_week_start, run.attempt"
                ),
                {
                    "now": claimed_at,
                    "version": pipeline_version,
                    "token": token,
                    "lease_expires_at": claimed_at + timedelta(seconds=lease_seconds),
                    "pipeline_name": PIPELINE_NAME,
                },
            ).mappings().one_or_none()
            if row is None:
                return None
            reset_at = connection.execute(
                text("SELECT last_reset_at FROM reporting.source_ledger_state WHERE id = 1")
            ).scalar_one_or_none()
            try:
                weeks = _target_weeks(
                    cast(date | None, row["requested_week_start"]),
                    now=claimed_at,
                    last_reset_at=cast(datetime | None, reset_at),
                    recompute_weeks=recompute_weeks,
                )
            except QueueValidationError:
                # A reset can freeze a week after it was queued. Resolve that
                # deterministic failure durably instead of retrying forever.
                connection.execute(
                    text(
                        "UPDATE reporting.pipeline_runs SET status = 'failed', finished_at = :now, "
                        "claim_token = NULL, heartbeat_at = NULL, lease_expires_at = NULL, "
                        "error_code = 'VALIDATE_FAILED', error_summary = :summary "
                        "WHERE id = :id AND claim_token = :token AND status = 'running'"
                    ),
                    {
                        "now": claimed_at,
                        "summary": _SAFE_ERROR_SUMMARIES["VALIDATE_FAILED"],
                        "id": row["id"],
                        "token": row["claim_token"],
                    },
                )
                return None
            connection.execute(
                text("UPDATE reporting.pipeline_runs SET target_weeks = :weeks WHERE id = :id"),
                {"weeks": list(weeks), "id": row["id"]},
            )
            return RunClaim(
                run_id=_row_uuid(row, "id"),
                claim_token=_row_uuid(row, "claim_token"),
                trigger_type=cast(TriggerType, row["trigger_type"]),
                requested_week_start=cast(date | None, row["requested_week_start"]),
                target_weeks=weeks,
                attempt=cast(int, row["attempt"]),
            )
    except IntegrityError:
        # A concurrent worker may have installed the single-active row between
        # candidate selection and UPDATE. Its transaction wins; this tick is quiet.
        return None


def heartbeat(
    engine: Engine,
    claim: RunClaim,
    *,
    now: datetime | None = None,
    lease_seconds: int = DEFAULT_LEASE_SECONDS,
) -> bool:
    heartbeat_at = now or utc_now()
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "UPDATE reporting.pipeline_runs SET heartbeat_at = :now, lease_expires_at = :expires "
                "WHERE id = :id AND claim_token = :token AND status = 'running'"
            ),
            {
                "now": heartbeat_at,
                "expires": heartbeat_at + timedelta(seconds=lease_seconds),
                "id": claim.run_id,
                "token": claim.claim_token,
            },
        )
    return result.rowcount == 1


def verify_claim_for_publication(connection: Connection, claim: RunClaim) -> None:
    """Lock and verify ownership inside the same transaction that publishes rows."""
    owned = connection.execute(
        text(
            "SELECT 1 FROM reporting.pipeline_runs "
            "WHERE id = :id AND claim_token = :token AND status = 'running' FOR UPDATE"
        ),
        {"id": claim.run_id, "token": claim.claim_token},
    ).scalar_one_or_none()
    if owned is None:
        raise LeaseLostError("pipeline run lease is no longer owned")


def finalize_success(
    engine: Engine,
    claim: RunClaim,
    metrics: RunMetrics,
    *,
    now: datetime | None = None,
) -> bool:
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "UPDATE reporting.pipeline_runs SET status = 'succeeded', finished_at = :now, "
                "rows_extracted = :rows_extracted, rows_transformed = :rows_transformed, "
                "rows_loaded = :rows_loaded, source_watermark = :source_watermark, "
                "claim_token = NULL, heartbeat_at = NULL, lease_expires_at = NULL, "
                "error_code = NULL, error_summary = NULL "
                "WHERE id = :id AND claim_token = :token AND status = 'running'"
            ),
            {
                "now": now or utc_now(),
                "rows_extracted": metrics.rows_extracted,
                "rows_transformed": metrics.rows_transformed,
                "rows_loaded": metrics.rows_loaded,
                "source_watermark": metrics.source_watermark,
                "id": claim.run_id,
                "token": claim.claim_token,
            },
        )
    return result.rowcount == 1


def _backoff(attempt: int, base_seconds: int) -> timedelta:
    return timedelta(seconds=base_seconds * (2 ** max(0, attempt - 1)))


def release_retryable(
    engine: Engine,
    claim: RunClaim,
    error_code: ErrorCode,
    *,
    now: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: int = DEFAULT_BACKOFF_SECONDS,
) -> bool:
    transition_at = now or utc_now()
    exhausted = claim.attempt >= max_attempts
    final_code = "MAX_ATTEMPTS_EXCEEDED" if exhausted else error_code
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "UPDATE reporting.pipeline_runs SET status = :status, finished_at = :finished_at, "
                "next_attempt_at = :next_attempt_at, claim_token = NULL, heartbeat_at = NULL, "
                "lease_expires_at = NULL, error_code = :error_code, error_summary = :error_summary "
                "WHERE id = :id AND claim_token = :token AND status = 'running'"
            ),
            {
                "status": "failed" if exhausted else "retryable",
                "finished_at": transition_at if exhausted else None,
                "next_attempt_at": None if exhausted else transition_at + _backoff(claim.attempt, backoff_seconds),
                "error_code": final_code,
                "error_summary": _SAFE_ERROR_SUMMARIES[final_code],
                "id": claim.run_id,
                "token": claim.claim_token,
            },
        )
    return result.rowcount == 1


def finalize_failure(
    engine: Engine,
    claim: RunClaim,
    error_code: ErrorCode,
    *,
    now: datetime | None = None,
) -> bool:
    with engine.begin() as connection:
        result = connection.execute(
            text(
                "UPDATE reporting.pipeline_runs SET status = 'failed', finished_at = :now, "
                "claim_token = NULL, heartbeat_at = NULL, lease_expires_at = NULL, "
                "error_code = :error_code, error_summary = :error_summary "
                "WHERE id = :id AND claim_token = :token AND status = 'running'"
            ),
            {
                "now": now or utc_now(),
                "error_code": error_code,
                "error_summary": _SAFE_ERROR_SUMMARIES[error_code],
                "id": claim.run_id,
                "token": claim.claim_token,
            },
        )
    return result.rowcount == 1


def recover_stale_runs(
    engine: Engine,
    *,
    now: datetime | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    backoff_seconds: int = DEFAULT_BACKOFF_SECONDS,
) -> int:
    """Reclaim only expired leases; heartbeating and terminal rows are untouched."""
    sweep_at = now or utc_now()
    recovered = 0
    with engine.begin() as connection:
        rows = connection.execute(
            text(
                "SELECT id, attempt FROM reporting.pipeline_runs "
                "WHERE pipeline_name = :pipeline_name AND status = 'running' "
                "AND lease_expires_at < :now FOR UPDATE SKIP LOCKED"
            ),
            {"pipeline_name": PIPELINE_NAME, "now": sweep_at},
        ).mappings().all()
        for row in rows:
            attempt = cast(int, row["attempt"])
            exhausted = attempt >= max_attempts
            connection.execute(
                text(
                    "UPDATE reporting.pipeline_runs SET status = :status, finished_at = :finished_at, "
                    "next_attempt_at = :next_attempt_at, claim_token = NULL, heartbeat_at = NULL, "
                    "lease_expires_at = NULL, error_code = :error_code, error_summary = :error_summary "
                    "WHERE id = :id AND status = 'running'"
                ),
                {
                    "status": "failed" if exhausted else "retryable",
                    "finished_at": sweep_at if exhausted else None,
                    "next_attempt_at": None if exhausted else sweep_at + _backoff(attempt, backoff_seconds),
                    "error_code": "MAX_ATTEMPTS_EXCEEDED" if exhausted else "STALE_ABANDONED",
                    "error_summary": _SAFE_ERROR_SUMMARIES[
                        "MAX_ATTEMPTS_EXCEEDED" if exhausted else "STALE_ABANDONED"
                    ],
                    "id": row["id"],
                },
            )
            recovered += 1
    return recovered
