"""Transactional extraction, loading, and Prefect flow integration tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.exc import SQLAlchemyError
from prefect.testing.utilities import prefect_test_harness

from pipelines.business_performance import flows
from pipelines.business_performance.cache import CacheConfigurationError
from pipelines.business_performance.flows import prefect_executor, upsert_weekly_performance_rows
from pipelines.business_performance.queue import RunClaim, claim_next, enqueue_cli, release_retryable
from pipelines.business_performance.runner import PipelineStageError, RunnerStatus, run_once
from process.business_performance import TransformError, WeeklyPerformanceRow

WEEK = date(2026, 7, 13)


def _seed_activity(engine: Engine) -> UUID:
    client_id = uuid4()
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO clients (id, display_name) VALUES (:id, 'Flow Test Client')"),
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
    enqueue_cli(pipeline_engine, requested_week_start=WEEK, now=datetime.now(UTC) - timedelta(seconds=1))
    with prefect_test_harness():
        result = run_once(pipeline_engine, prefect_executor)
    assert result.status == RunnerStatus.SUCCEEDED

    with pipeline_engine.connect() as connection:
        report = connection.execute(
            text(
                "SELECT warehouse, client_id, week_start, inbound_units_count, outbound_orders_count "
                "FROM reporting.weekly_warehouse_client_performance"
            )
        ).mappings().one()
        run = connection.execute(
            text("SELECT status, rows_extracted, rows_transformed, rows_loaded FROM reporting.pipeline_runs")
        ).mappings().one()
    assert report == {
        "warehouse": "los_angeles",
        "client_id": client_id,
        "week_start": WEEK,
        "inbound_units_count": 12,
        "outbound_orders_count": 1,
    }
    assert run == {"status": "succeeded", "rows_extracted": 2, "rows_transformed": 1, "rows_loaded": 1}


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
    row = WeeklyPerformanceRow("los_angeles", str(client_id), WEEK, 12, 1, 0, 0, Decimal(0))
    first = upsert_weekly_performance_rows.fn([row], claim)
    assert first.rows_loaded == 1
    assert release_retryable(pipeline_engine, claim, "DB_UNAVAILABLE")
    reclaimed = claim_next(pipeline_engine, now=datetime.now(UTC) + timedelta(minutes=2))
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


def test_flow_aborts_without_finalization_when_lease_is_lost(monkeypatch: pytest.MonkeyPatch) -> None:
    claim = RunClaim(uuid4(), uuid4(), "cli", WEEK, (WEEK,), 1)

    def lose_lease(_weeks: tuple[date, ...]) -> None:
        raise flows.LeaseLostError("lost")

    monkeypatch.setattr(flows, "extract_warehouse_client_activity", lose_lease)
    with pytest.raises(flows.LeaseLostError):
        flows.weekly_warehouse_client_performance.fn(claim, "test-version")
