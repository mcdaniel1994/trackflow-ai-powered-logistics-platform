"""Transactional extraction, loading, and Prefect flow integration tests."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
import httpx
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from prefect.testing.utilities import prefect_test_harness

from pipelines.business_performance import flows
from pipelines.business_performance.cache import CacheConfigurationError
from pipelines.business_performance.flows import (
    prefect_executor,
    upsert_weekly_performance_rows,
)
from pipelines.business_performance.queue import (
    LeaseLostError,
    RunClaim,
    claim_next,
    enqueue_cli,
    release_retryable,
)
from pipelines.business_performance.runner import (
    PipelineStageError,
    RunnerStatus,
    run_once,
)
from process.business_performance import TransformError, WeeklyPerformanceRow

WEEK = date(2026, 7, 13)


def test_prefect_executor_uses_deterministic_name_and_honors_abort() -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 2)
    assert (
        flows._flow_run_name(claim) == f"business-performance-{claim.run_id}-attempt-2"
    )
    abort = Event()
    abort.set()
    with pytest.raises(LeaseLostError):
        prefect_executor(object(), claim, abort)


def test_publish_run_summary_writes_only_fixed_metrics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = uuid4()
    fake_source = tmp_path / "one" / "two" / "flows.py"
    monkeypatch.setenv("REPORTING_EVAL_OUTPUT_ENABLED", "true")
    monkeypatch.setattr(flows, "Path", lambda _value: fake_source)
    flows.publish_run_summary.fn(run_id, flows.RunMetrics(3, 2, 1))
    output = tmp_path / "eval" / "business_performance" / f"{run_id}.json"
    assert output.read_text() == (
        f'{{"rows_extracted": 3, "rows_loaded": 1, "rows_transformed": 2, '
        f'"run_id": "{run_id}", "status": "succeeded"}}\n'
    )


def test_close_orphan_handles_final_and_running_prefect_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ClientContext:
        def __init__(self, client: object) -> None:
            self.client = client

        async def __aenter__(self) -> object:
            return self.client

        async def __aexit__(self, *_args: object) -> None:
            return None

    final_client = SimpleNamespace(
        read_flow_run=lambda _run_id: asyncio.sleep(
            0,
            result=SimpleNamespace(
                id=uuid4(), state=SimpleNamespace(is_final=lambda: True)
            ),
        )
    )
    monkeypatch.setattr(flows, "get_client", lambda: ClientContext(final_client))
    assert asyncio.run(flows._close_orphan(uuid4(), "fallback")) is False

    running = SimpleNamespace(id=uuid4(), state=SimpleNamespace(is_final=lambda: False))
    closed: list[UUID] = []

    async def read_flow_runs(**_kwargs: object) -> list[object]:
        return [running]

    async def set_flow_run_state(
        run_id: UUID, *_args: object, **_kwargs: object
    ) -> None:
        closed.append(run_id)

    running_client = SimpleNamespace(
        read_flow_runs=read_flow_runs,
        set_flow_run_state=set_flow_run_state,
    )
    monkeypatch.setattr(flows, "get_client", lambda: ClientContext(running_client))
    assert asyncio.run(flows._close_orphan(None, "fallback")) is True
    assert closed == [running.id]


def _seed_activity(engine: Engine) -> UUID:
    client_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO clients (id, display_name) VALUES (:id, 'Flow Test Client')"
            ),
            {"id": client_id},
        )
        sku_id = connection.execute(
            text(
                "INSERT INTO skus (name, sku, client_id, min_stock_threshold, category, warehouse) "
                "VALUES ('Flow SKU', 'FLOW-1', :client_id, 0, 'fashion', 'LA') RETURNING id"
            ),
            {"client_id": client_id},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO stock_entries (sku_id, quantity, reference, warehouse, created_at, user_uuid) "
                "VALUES (:sku_id, 12, 'flow-inbound', 'LA', :created_at, :user_uuid)"
            ),
            {
                "sku_id": sku_id,
                "created_at": datetime(2026, 7, 13, 10, 0, tzinfo=UTC),
                "user_uuid": str(uuid4()),
            },
        )
        connection.execute(
            text(
                "INSERT INTO stock_exits "
                "(sku_id, quantity, exit_type, tracking_number, warehouse, created_at, user_uuid) "
                "VALUES (:sku_id, 2, 'dispatch', 'FLOW-TRACK', 'LA', :created_at, :user_uuid)"
            ),
            {
                "sku_id": sku_id,
                "created_at": datetime(2026, 7, 14, 10, 0, tzinfo=UTC),
                "user_uuid": str(uuid4()),
            },
        )
    return client_id


def test_prefect_flow_extracts_transforms_loads_and_finalizes(
    pipeline_engine: Engine,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    client_id = _seed_activity(pipeline_engine)
    enqueue_cli(
        pipeline_engine,
        requested_week_start=WEEK,
        now=datetime.now(UTC) - timedelta(seconds=1),
    )
    with prefect_test_harness():
        result = run_once(pipeline_engine, prefect_executor)
    assert result.status == RunnerStatus.SUCCEEDED

    with pipeline_engine.connect() as connection:
        report = (
            connection.execute(
                text(
                    "SELECT warehouse, client_id, week_start, inbound_units_count, outbound_orders_count "
                    "FROM reporting.weekly_warehouse_client_performance"
                )
            )
            .mappings()
            .one()
        )
        run = (
            connection.execute(
                text(
                    "SELECT status, rows_extracted, rows_transformed, rows_loaded FROM reporting.pipeline_runs"
                )
            )
            .mappings()
            .one()
        )
    assert report == {
        "warehouse": "los_angeles",
        "client_id": client_id,
        "week_start": WEEK,
        "inbound_units_count": 12,
        "outbound_orders_count": 1,
    }
    assert run == {
        "status": "succeeded",
        "rows_extracted": 2,
        "rows_transformed": 1,
        "rows_loaded": 1,
    }


def test_failed_load_rolls_back_and_preserves_previous_success(
    pipeline_engine: Engine,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    client_id = _seed_activity(pipeline_engine)
    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.weekly_warehouse_client_performance "
                "(warehouse, client_id, week_start, inbound_units_count, outbound_orders_count, "
                "stockout_events_count, discrepancy_events_count, discrepancy_rate, computed_at) "
                "VALUES ('los_angeles', :client_id, :week, 99, 5, 0, 0, 0, :computed_at)"
            ),
            {"client_id": client_id, "week": WEEK, "computed_at": datetime.now(UTC)},
        )
    enqueue_cli(pipeline_engine, requested_week_start=WEEK)
    claim = claim_next(pipeline_engine)
    assert claim is not None
    invalid = WeeklyPerformanceRow(
        warehouse="los_angeles",
        client_id=str(uuid4()),
        week_start=WEEK,
        inbound_units_count=1,
        outbound_orders_count=0,
        stockout_events_count=0,
        discrepancy_events_count=0,
        discrepancy_rate=Decimal(0),
    )
    with pytest.raises(IntegrityError):
        upsert_weekly_performance_rows.fn([invalid], claim)
    assert release_retryable(pipeline_engine, claim, "LOAD_FAILED")
    with pipeline_engine.connect() as connection:
        inbound = connection.execute(
            text(
                "SELECT inbound_units_count FROM reporting.weekly_warehouse_client_performance "
                "WHERE client_id = :client_id AND week_start = :week"
            ),
            {"client_id": client_id, "week": WEEK},
        ).scalar_one()
    assert inbound == 99


def test_idempotent_load_removes_only_stale_rows_in_target_week(
    pipeline_engine: Engine,
    database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    client_id = _seed_activity(pipeline_engine)
    enqueue_cli(pipeline_engine, requested_week_start=WEEK)
    claim = claim_next(pipeline_engine)
    assert claim is not None
    row = WeeklyPerformanceRow(
        "los_angeles", str(client_id), WEEK, 12, 1, 0, 0, Decimal(0)
    )
    first = upsert_weekly_performance_rows.fn([row], claim)
    assert first.rows_loaded == 1
    assert release_retryable(pipeline_engine, claim, "DB_UNAVAILABLE")
    reclaimed = claim_next(
        pipeline_engine, now=datetime.now(UTC) + timedelta(minutes=2)
    )
    assert reclaimed is not None
    second = upsert_weekly_performance_rows.fn([row], reclaimed)
    assert second.rows_loaded == 1
    assert release_retryable(pipeline_engine, reclaimed, "DB_UNAVAILABLE")
    with pipeline_engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM reporting.weekly_warehouse_client_performance")
        ).scalar_one()
    assert count == 1


@pytest.mark.parametrize(
    ("failure", "expected_retryable", "expected_code"),
    [
        (TransformError("bad source"), False, "VALIDATE_FAILED"),
        (CacheConfigurationError("partial config"), False, "VALIDATE_FAILED"),
        (SQLAlchemyError("db down"), True, "DB_UNAVAILABLE"),
        (RuntimeError("load failed"), True, "EXTRACT_FAILED"),
    ],
)
def test_flow_propagates_safe_stage_failures_without_exception_details(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    expected_retryable: bool,
    expected_code: str,
) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)

    def fail_extract(_weeks: tuple[date, ...]) -> None:
        raise failure

    monkeypatch.setattr(flows, "extract_warehouse_client_activity", fail_extract)
    with pytest.raises(PipelineStageError) as raised:
        flows.weekly_warehouse_client_performance.fn(claim, "test-version")
    assert str(raised.value) == "pipeline stage failed"
    assert raised.value.stage == "extract"
    assert raised.value.error_code == expected_code
    assert raised.value.error_type == type(failure).__name__
    assert raised.value.retryable is expected_retryable
    assert "bad source" not in str(raised.value)


def test_flow_aborts_without_finalization_when_lease_is_lost(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)

    def lose_lease(_weeks: tuple[date, ...]) -> None:
        raise flows.LeaseLostError("lost")

    monkeypatch.setattr(flows, "extract_warehouse_client_activity", lose_lease)
    with pytest.raises(flows.LeaseLostError):
        flows.weekly_warehouse_client_performance.fn(claim, "test-version")


def test_prefect_records_propagated_pipeline_failure_as_failed_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)

    def fail_extract(_weeks: tuple[date, ...]) -> None:
        raise TransformError("private record detail")

    monkeypatch.setattr(flows, "extract_warehouse_client_activity", fail_extract)
    monkeypatch.setattr(flows, "record_prefect_flow_run", lambda *_args: True)
    monkeypatch.setattr(flows, "claim_is_owned", lambda *_args: True)
    monkeypatch.setattr(flows, "record_stage", lambda *_args: True)
    with prefect_test_harness():
        state = flows.weekly_warehouse_client_performance(
            claim, "test-version", return_state=True
        )
    assert state.is_failed()
    with pytest.raises(PipelineStageError) as raised:
        state.result()
    assert raised.value.stage == "extract"
    assert "private record detail" not in str(raised.value)


def test_known_prefect_transport_failure_has_orchestration_taxonomy() -> None:
    error = flows._stage_failure("transform", httpx.ConnectError("private endpoint"))
    assert error.error_code == "ORCHESTRATION_FAILED"
    assert error.retryable is True


def test_unknown_transform_failure_is_internal_and_load_failure_stays_load_specific() -> (
    None
):
    assert (
        flows._stage_failure("transform", RuntimeError("private")).error_code
        == "INTERNAL_FAILED"
    )
    assert (
        flows._stage_failure("load", RuntimeError("private")).error_code
        == "LOAD_FAILED"
    )


def test_orphan_reconciliation_is_noop_without_running_rows(
    pipeline_engine: Engine,
) -> None:
    assert flows.reconcile_orphaned_flow_runs(pipeline_engine) == 0
