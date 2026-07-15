"""DB-backed queue, lease, CAS, retry, and advisory-lock proofs."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text

from pipelines.business_performance.locks import REPORTING_PIPELINE_LOCK_KEY
from pipelines.business_performance.queue import (
    LeaseLostError,
    QueueValidationError,
    RunClaim,
    RunMetrics,
    claim_next,
    enqueue_cli,
    enqueue_manual,
    enqueue_scheduled,
    finalize_failure,
    finalize_success,
    heartbeat,
    recover_stale_runs,
    release_retryable,
    verify_claim_for_publication,
)
from pipelines.business_performance.runner import (
    PermanentRunError,
    RunnerStatus,
    TransientRunError,
    run_once,
)

BASE_TIME = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
MONDAY = date(2026, 7, 13)


def _run_row(engine: Engine, run_id: UUID) -> dict[str, object]:
    with engine.connect() as connection:
        return dict(
            connection.execute(
                text("SELECT * FROM reporting.pipeline_runs WHERE id = :id"),
                {"id": run_id},
            ).mappings().one()
        )


def _claim_requested(engine: Engine, *, now: datetime = BASE_TIME) -> RunClaim:
    enqueue_cli(engine, now=now - timedelta(seconds=1))
    claim = claim_next(engine, now=now)
    assert claim is not None
    return claim


def test_atomic_claim_allows_exactly_one_concurrent_worker(pipeline_engine: Engine) -> None:
    enqueue_cli(pipeline_engine, now=BASE_TIME - timedelta(seconds=2))
    enqueue_cli(pipeline_engine, now=BASE_TIME - timedelta(seconds=1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(lambda _: claim_next(pipeline_engine, now=BASE_TIME), range(2)))
    assert sum(claim is not None for claim in claims) == 1
    with pipeline_engine.connect() as connection:
        counts = connection.execute(
            text("SELECT status, count(*) FROM reporting.pipeline_runs GROUP BY status")
        ).all()
    assert set(counts) == {("requested", 1), ("running", 1)}


def test_manual_request_queues_behind_active_and_coalesces(pipeline_engine: Engine) -> None:
    active = _claim_requested(pipeline_engine)
    requested = enqueue_manual(
        pipeline_engine,
        requested_by=str(uuid4()),
        requested_week_start=MONDAY,
        now=BASE_TIME,
    )
    duplicate = enqueue_manual(
        pipeline_engine,
        requested_by=str(uuid4()),
        requested_week_start=MONDAY,
        now=BASE_TIME + timedelta(seconds=1),
    )
    forced = enqueue_manual(
        pipeline_engine,
        requested_by=str(uuid4()),
        requested_week_start=MONDAY,
        force_refresh=True,
        now=BASE_TIME + timedelta(seconds=2),
    )
    assert requested == duplicate
    assert forced != requested
    assert _run_row(pipeline_engine, requested)["status"] == "requested"
    assert finalize_success(pipeline_engine, active, RunMetrics(0, 0, 0), now=BASE_TIME)
    next_claim = claim_next(pipeline_engine, now=BASE_TIME + timedelta(seconds=3))
    assert next_claim is not None
    assert next_claim.run_id == requested


def test_persisted_requested_week_survives_claim_restart(pipeline_engine: Engine) -> None:
    run_id = enqueue_manual(
        pipeline_engine,
        requested_by=str(uuid4()),
        requested_week_start=MONDAY,
        now=BASE_TIME,
    )
    claim = claim_next(pipeline_engine, now=BASE_TIME + timedelta(hours=1))
    assert claim is not None
    assert claim.run_id == run_id
    assert claim.requested_week_start == MONDAY
    assert claim.target_weeks == (MONDAY,)
    assert _run_row(pipeline_engine, run_id)["target_weeks"] == [MONDAY]


def test_default_window_is_resolved_and_reset_clipped_at_claim(pipeline_engine: Engine) -> None:
    with pipeline_engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.source_ledger_state SET last_reset_at = :reset_at WHERE id = 1"),
            {"reset_at": datetime(2026, 7, 6, 0, 0, tzinfo=UTC)},
        )
    claim = _claim_requested(pipeline_engine)
    assert claim.target_weeks == (date(2026, 7, 6), date(2026, 7, 13))


def test_frozen_or_non_monday_manual_week_is_rejected(pipeline_engine: Engine) -> None:
    with pytest.raises(QueueValidationError, match="ISO Monday"):
        enqueue_manual(pipeline_engine, requested_by="admin", requested_week_start=date(2026, 7, 14))
    with pipeline_engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.source_ledger_state SET last_reset_at = :reset_at WHERE id = 1"),
            {"reset_at": datetime(2026, 7, 14, 0, 0, tzinfo=UTC)},
        )
    with pytest.raises(QueueValidationError, match="precedes last ledger reset"):
        enqueue_manual(pipeline_engine, requested_by="admin", requested_week_start=MONDAY)


def test_reset_after_enqueue_fails_request_instead_of_retrying_forever(pipeline_engine: Engine) -> None:
    run_id = enqueue_manual(pipeline_engine, requested_by="admin", requested_week_start=MONDAY)
    with pipeline_engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.source_ledger_state SET last_reset_at = :reset_at WHERE id = 1"),
            {"reset_at": datetime(2026, 7, 14, 0, 0, tzinfo=UTC)},
        )
    assert claim_next(pipeline_engine, now=BASE_TIME) is None
    row = _run_row(pipeline_engine, run_id)
    assert row["status"] == "failed"
    assert row["error_code"] == "VALIDATE_FAILED"


def test_retry_backoff_blocks_early_reclaim(pipeline_engine: Engine) -> None:
    first = _claim_requested(pipeline_engine)
    assert release_retryable(pipeline_engine, first, "DB_UNAVAILABLE", now=BASE_TIME)
    row = _run_row(pipeline_engine, first.run_id)
    assert row["status"] == "retryable"
    assert row["next_attempt_at"] == BASE_TIME + timedelta(minutes=1)
    assert claim_next(pipeline_engine, now=BASE_TIME + timedelta(seconds=59)) is None
    second = claim_next(pipeline_engine, now=BASE_TIME + timedelta(minutes=1))
    assert second is not None
    assert second.attempt == 2


def test_fifth_transient_failure_is_terminal(pipeline_engine: Engine) -> None:
    claim = _claim_requested(pipeline_engine)
    with pipeline_engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.pipeline_runs SET attempt = 5 WHERE id = :id"),
            {"id": claim.run_id},
        )
    final_claim = RunClaim(
        claim.run_id,
        claim.claim_token,
        claim.trigger_type,
        claim.requested_week_start,
        claim.target_weeks,
        5,
    )
    assert release_retryable(pipeline_engine, final_claim, "DB_UNAVAILABLE", now=BASE_TIME)
    row = _run_row(pipeline_engine, claim.run_id)
    assert row["status"] == "failed"
    assert row["error_code"] == "MAX_ATTEMPTS_EXCEEDED"
    assert row["next_attempt_at"] is None


def test_stale_recovery_uses_lease_and_heartbeat_only(pipeline_engine: Engine) -> None:
    claim = _claim_requested(pipeline_engine)
    assert heartbeat(pipeline_engine, claim, now=BASE_TIME + timedelta(minutes=5), lease_seconds=600)
    assert recover_stale_runs(pipeline_engine, now=BASE_TIME + timedelta(minutes=11)) == 0
    assert _run_row(pipeline_engine, claim.run_id)["status"] == "running"
    assert recover_stale_runs(pipeline_engine, now=BASE_TIME + timedelta(minutes=16)) == 1
    assert _run_row(pipeline_engine, claim.run_id)["status"] == "retryable"


def test_stale_recovery_fails_max_attempt_and_never_moves_terminal_rows(pipeline_engine: Engine) -> None:
    claim = _claim_requested(pipeline_engine)
    with pipeline_engine.begin() as connection:
        connection.execute(
            text("UPDATE reporting.pipeline_runs SET attempt = 5 WHERE id = :id"),
            {"id": claim.run_id},
        )
    assert recover_stale_runs(pipeline_engine, now=BASE_TIME + timedelta(minutes=11)) == 1
    assert _run_row(pipeline_engine, claim.run_id)["error_code"] == "MAX_ATTEMPTS_EXCEEDED"
    assert recover_stale_runs(pipeline_engine, now=BASE_TIME + timedelta(days=1)) == 0


def test_old_worker_cannot_heartbeat_publish_or_finalize_after_reclaim(pipeline_engine: Engine) -> None:
    claim = _claim_requested(pipeline_engine)
    assert recover_stale_runs(pipeline_engine, now=BASE_TIME + timedelta(minutes=11)) == 1
    assert heartbeat(pipeline_engine, claim, now=BASE_TIME + timedelta(minutes=12)) is False
    with pytest.raises(LeaseLostError):
        with pipeline_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO reporting.incomplete_weeks (week_start, reason) "
                    "VALUES (:week_start, 'zombie-test')"
                ),
                {"week_start": MONDAY},
            )
            verify_claim_for_publication(connection, claim)
    with pipeline_engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM reporting.incomplete_weeks")).scalar_one() == 0
    assert finalize_success(pipeline_engine, claim, RunMetrics(1, 1, 1), now=BASE_TIME) is False
    assert finalize_failure(pipeline_engine, claim, "LOAD_FAILED", now=BASE_TIME) is False


def test_runner_releases_claim_when_advisory_lock_is_held(pipeline_engine: Engine) -> None:
    enqueue_cli(pipeline_engine, now=datetime.now(UTC) - timedelta(seconds=1))
    with pipeline_engine.connect() as lock_connection:
        assert lock_connection.execute(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": REPORTING_PIPELINE_LOCK_KEY},
        ).scalar_one()
        try:
            result = run_once(pipeline_engine, lambda _engine, _claim: RunMetrics(0, 0, 0))
        finally:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:key)"),
                {"key": REPORTING_PIPELINE_LOCK_KEY},
            )
    assert result.status == RunnerStatus.RETRYABLE
    row = _run_row(pipeline_engine, UUID(result.run_id or ""))
    assert row["status"] == "retryable"
    assert row["error_code"] == "LOCK_UNAVAILABLE"


def test_runner_success_and_classified_failures(pipeline_engine: Engine) -> None:
    enqueue_cli(pipeline_engine, now=datetime.now(UTC) - timedelta(seconds=3))
    succeeded = run_once(pipeline_engine, lambda _engine, _claim: RunMetrics(3, 2, 1))
    assert succeeded.status == RunnerStatus.SUCCEEDED
    success_row = _run_row(pipeline_engine, UUID(succeeded.run_id or ""))
    assert (success_row["rows_extracted"], success_row["rows_transformed"], success_row["rows_loaded"]) == (3, 2, 1)

    enqueue_cli(pipeline_engine, now=datetime.now(UTC) - timedelta(seconds=2))

    def permanent(_engine: Engine, _claim: RunClaim) -> RunMetrics:
        raise PermanentRunError("VALIDATE_FAILED")

    failed = run_once(pipeline_engine, permanent)
    assert failed.status == RunnerStatus.FAILED

    enqueue_cli(pipeline_engine, now=datetime.now(UTC) - timedelta(seconds=1))

    def transient(_engine: Engine, _claim: RunClaim) -> RunMetrics:
        raise TransientRunError("DB_UNAVAILABLE")

    retryable = run_once(pipeline_engine, transient)
    assert retryable.status == RunnerStatus.RETRYABLE

    enqueue_cli(pipeline_engine, now=datetime.now(UTC) - timedelta(seconds=1))

    def unexpected(_engine: Engine, _claim: RunClaim) -> RunMetrics:
        raise RuntimeError("sensitive implementation detail")

    unknown = run_once(pipeline_engine, unexpected)
    assert unknown.status == RunnerStatus.RETRYABLE
    unknown_row = _run_row(pipeline_engine, UUID(unknown.run_id or ""))
    assert unknown_row["error_code"] == "EXTRACT_FAILED"
    assert "sensitive" not in str(unknown_row["error_summary"])


def test_runner_is_idle_when_queue_is_empty(pipeline_engine: Engine) -> None:
    result = run_once(pipeline_engine, lambda _engine, _claim: RunMetrics(0, 0, 0))
    assert result.status == RunnerStatus.IDLE


def test_scheduled_and_manual_metadata_are_distinct(pipeline_engine: Engine) -> None:
    scheduled = enqueue_scheduled(pipeline_engine, date(2026, 7, 15), now=BASE_TIME)
    assert scheduled is not None
    manual = enqueue_manual(
        pipeline_engine,
        requested_by="11111111-1111-4111-8111-111111111111",
        now=BASE_TIME,
    )
    scheduled_row = _run_row(pipeline_engine, scheduled)
    manual_row = _run_row(pipeline_engine, manual)
    assert scheduled_row["trigger_type"] == "scheduled"
    assert scheduled_row["requested_by"] == "system"
    assert scheduled_row["scheduled_business_date"] == date(2026, 7, 15)
    assert manual_row["trigger_type"] == "manual"
    assert manual_row["scheduled_business_date"] is None
