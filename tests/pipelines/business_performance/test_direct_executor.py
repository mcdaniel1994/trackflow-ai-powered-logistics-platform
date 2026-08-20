"""Direct SQL executor contract, retry, CAS-stage, and parity proofs."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from pipelines.business_performance import direct_executor
from pipelines.business_performance.direct_executor import direct_sql_executor
from pipelines.business_performance.queue import (
    LeaseLostError,
    RunClaim,
    claim_next,
    enqueue_cli,
)
from pipelines.business_performance.rollups import capture_rollup_window
from pipelines.business_performance.runner import (
    PipelineStageError,
)

WEEK = date(2026, 7, 13)
FIXED_CUTOFF = datetime(2026, 7, 20, tzinfo=UTC)


def _seed_activity(engine: Engine) -> UUID:
    client_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clients (id, display_name) "
                "VALUES (:id, 'Direct Executor Test')"
            ),
            {"id": client_id},
        )
        sku_id = int(
            connection.scalar(
                text(
                    "INSERT INTO skus "
                    "(name, sku, client_id, min_stock_threshold, category, warehouse) "
                    "VALUES ('Direct SKU', 'DIRECT-1', :client_id, 0, 'fashion', 'LA') "
                    "RETURNING id"
                ),
                {"client_id": client_id},
            )
        )
        connection.execute(
            text(
                "INSERT INTO stock_entries "
                "(sku_id, quantity, reference, warehouse, created_at, user_uuid) "
                "VALUES (:sku, 12, 'direct-inbound', 'LA', :at, :user)"
            ),
            {
                "sku": sku_id,
                "at": datetime(2026, 7, 13, 10, tzinfo=UTC),
                "user": str(uuid4()),
            },
        )
        connection.execute(
            text(
                "INSERT INTO stock_exits "
                "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                "VALUES (:sku, 2, 'dispatch', 'DIRECT-TRACK', 'LA', :at, :user)"
            ),
            {
                "sku": sku_id,
                "at": datetime(2026, 7, 14, 10, tzinfo=UTC),
                "user": str(uuid4()),
            },
        )
    return client_id


def _snapshot(engine: Engine) -> tuple[list[tuple[object, ...]], list[tuple[object, ...]]]:
    with engine.connect() as connection:
        hourly = connection.execute(
            text(
                "SELECT bucket_start, warehouse, client_id, inbound_movement_count, "
                "inbound_units, dispatch_order_count, dispatch_units, loss_movement_count, "
                "loss_units, stockout_count, discrepancy_count, source_cutoff_at, pipeline_version "
                "FROM reporting.hourly_activity_rollups "
                "ORDER BY bucket_start, warehouse, client_id"
            )
        ).all()
        weekly = connection.execute(
            text(
                "SELECT warehouse, client_id, week_start, inbound_units_count, "
                "outbound_orders_count, stockout_events_count, discrepancy_events_count, "
                "discrepancy_rate FROM reporting.weekly_warehouse_client_performance "
                "ORDER BY week_start, warehouse, client_id"
            )
        ).all()
    return [tuple(row) for row in hourly], [tuple(row) for row in weekly]


def test_direct_executor_records_all_stages_unconditionally(
    pipeline_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_activity(pipeline_engine)
    enqueue_cli(
        pipeline_engine,
        requested_week_start=WEEK,
        now=FIXED_CUTOFF - timedelta(seconds=1),
    )
    claim = claim_next(pipeline_engine, now=FIXED_CUTOFF)
    assert claim is not None
    monkeypatch.setattr(
        direct_executor,
        "capture_rollup_window",
        lambda engine, used_claim: capture_rollup_window(
            engine,
            used_claim,
            now=FIXED_CUTOFF,
        ),
    )

    metrics = direct_sql_executor(pipeline_engine, claim, Event())

    assert metrics.source_cutoff_at == FIXED_CUTOFF
    with pipeline_engine.connect() as connection:
        current_stage = connection.scalar(
            text(
                "SELECT current_stage FROM reporting.pipeline_runs WHERE id = :id"
            ),
            {"id": claim.run_id},
        )
    assert current_stage == "load"


def test_direct_executor_refuses_missing_claim_before_computation(
    pipeline_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)
    monkeypatch.setattr(
        direct_executor,
        "capture_rollup_window",
        lambda *_args: pytest.fail("unowned claim reached SQL computation"),
    )
    with pytest.raises(LeaseLostError):
        direct_sql_executor(pipeline_engine, claim, Event())


def test_direct_executor_refuses_stage_when_cas_recording_fails(
    pipeline_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)
    monkeypatch.setattr(direct_executor, "claim_is_owned", lambda *_args: True)
    monkeypatch.setattr(direct_executor, "record_stage", lambda *_args: False)
    with pytest.raises(LeaseLostError):
        direct_executor._begin_stage(
            pipeline_engine,
            claim,
            "extract",
            Event(),
        )


def test_direct_executor_honors_abort_between_stages(
    pipeline_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _seed_activity(pipeline_engine)
    enqueue_cli(
        pipeline_engine,
        requested_week_start=WEEK,
        now=FIXED_CUTOFF - timedelta(seconds=1),
    )
    claim = claim_next(pipeline_engine, now=FIXED_CUTOFF)
    assert claim is not None
    abort = Event()
    def capture(engine: Engine, used_claim: RunClaim) -> object:
        result = capture_rollup_window(engine, used_claim, now=FIXED_CUTOFF)
        abort.set()
        return result

    monkeypatch.setattr(direct_executor, "capture_rollup_window", capture)
    monkeypatch.setattr(
        direct_executor,
        "compute_hourly_rollups",
        lambda *_args: pytest.fail("aborted claim reached transform"),
    )
    with pytest.raises(LeaseLostError):
        direct_sql_executor(pipeline_engine, claim, abort)


def test_direct_executor_uses_three_transient_only_attempts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    sleeps: list[float] = []

    def transient_then_success() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise SQLAlchemyError("connection refused")
        return "ok"

    monkeypatch.setattr(
        "pipelines.business_performance.direct_executor.time.sleep",
        sleeps.append,
    )
    assert direct_executor._run_sql(transient_then_success) == "ok"
    assert attempts == 3
    assert sleeps == [10.0, 10.0]

    attempts = 0

    def nontransient() -> str:
        nonlocal attempts
        attempts += 1
        raise SQLAlchemyError("permission denied")

    with pytest.raises(SQLAlchemyError):
        direct_executor._run_sql(nontransient)
    assert attempts == 1


@pytest.mark.parametrize(
    ("stage", "failure", "expected_code"),
    [
        ("extract", SQLAlchemyError("connection refused"), "DB_UNAVAILABLE"),
        ("extract", ConnectionRefusedError("private host"), "DB_UNAVAILABLE"),
        ("extract", SQLAlchemyError("permission denied"), "EXTRACT_FAILED"),
        ("transform", SQLAlchemyError("permission denied"), "INTERNAL_FAILED"),
        ("load", SQLAlchemyError("permission denied"), "LOAD_FAILED"),
        ("extract", RuntimeError("private"), "EXTRACT_FAILED"),
        ("transform", RuntimeError("private"), "INTERNAL_FAILED"),
        ("load", RuntimeError("postgresql://user:secret@private/report"), "LOAD_FAILED"),
    ],
)
def test_direct_executor_preserves_safe_failure_taxonomy(
    stage: str,
    failure: Exception,
    expected_code: str,
) -> None:
    mapped = direct_executor._stage_failure(stage, failure)
    assert isinstance(mapped, PipelineStageError)
    assert mapped.stage == stage
    assert mapped.error_code == expected_code
    assert mapped.error_type == type(failure).__name__
    assert mapped.retryable is True
    assert "secret" not in str(mapped)
    assert "private" not in str(mapped)


@pytest.mark.parametrize(
    ("failing_stage", "expected_code"),
    [
        ("extract", "EXTRACT_FAILED"),
        ("transform", "INTERNAL_FAILED"),
        ("load", "LOAD_FAILED"),
    ],
)
def test_direct_executor_maps_stage_failures_without_details(
    pipeline_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
    failing_stage: str,
    expected_code: str,
) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)
    window = SimpleNamespace(
        rows_scanned=0,
        source_cutoff_at=FIXED_CUTOFF,
    )
    monkeypatch.setattr(direct_executor, "_begin_stage", lambda *_args: 0.0)
    monkeypatch.setattr(direct_executor, "_complete_stage", lambda *_args: None)
    monkeypatch.setattr(
        direct_executor,
        "capture_rollup_window",
        lambda *_args: (
            (_ for _ in ()).throw(RuntimeError("private extract"))
            if failing_stage == "extract"
            else window
        ),
    )
    monkeypatch.setattr(
        direct_executor,
        "compute_hourly_rollups",
        lambda *_args: (
            (_ for _ in ()).throw(RuntimeError("private transform"))
            if failing_stage == "transform"
            else []
        ),
    )
    monkeypatch.setattr(direct_executor, "rollup_cutover_enabled", lambda: False)
    monkeypatch.setattr(
        direct_executor,
        "publish_hourly_rollups",
        lambda *_args, **_kwargs: (
            (_ for _ in ()).throw(RuntimeError("private load"))
            if failing_stage == "load"
            else 0
        ),
    )

    with pytest.raises(PipelineStageError) as raised:
        direct_sql_executor(pipeline_engine, claim, Event())
    assert raised.value.stage == failing_stage
    assert raised.value.error_code == expected_code
    assert "private" not in str(raised.value)
