"""Phase 3 reporting-schema constraints, indexes, and cleanup invariants."""

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, inspect
from sqlalchemy import select as sa_select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

from central_api.domains.inventory.models import Client
from central_api.domains.reporting.models import (
    HourlyActivityRollup,
    IncompleteWeek,
    PipelineRun,
    RollupState,
    SourceLedgerState,
    WeeklyWarehouseClientPerformance,
)

MONDAY = date(2026, 7, 13)


def _weekly_row(client_id: object, **overrides: object) -> WeeklyWarehouseClientPerformance:
    values: dict[str, object] = {
        "warehouse": "los_angeles",
        "client_id": client_id,
        "week_start": MONDAY,
        "inbound_units_count": 20,
        "outbound_orders_count": 4,
        "stockout_events_count": 1,
        "discrepancy_events_count": 1,
        "discrepancy_rate": Decimal("0.25"),
    }
    values.update(overrides)
    return WeeklyWarehouseClientPerformance(**values)


def _run(**overrides: object) -> PipelineRun:
    values: dict[str, object] = {
        "pipeline_name": "weekly_warehouse_client_performance",
        "trigger_type": "manual",
        "requested_by": "11111111-1111-4111-8111-111111111111",
        "status": "requested",
    }
    values.update(overrides)
    return PipelineRun(**values)


def test_reporting_schema_tables_columns_and_singleton_are_present(engine: Engine) -> None:
    inspector = inspect(engine)
    assert set(inspector.get_table_names(schema="reporting")) == {
        "hourly_activity_rollups",
        "incomplete_weeks",
        "pipeline_run_attempts",
        "pipeline_runs",
        "rollup_state",
        "source_ledger_state",
        "weekly_warehouse_client_performance",
        "worker_heartbeats",
    }
    pipeline_columns = {column["name"] for column in inspector.get_columns("pipeline_runs", schema="reporting")}
    assert {
        "requested_week_start",
        "target_weeks",
        "claim_token",
        "heartbeat_at",
        "lease_expires_at",
        "cache_nonce",
        "prefect_flow_run_id",
        "current_stage",
        "stage_started_at",
        "scheduled_for",
    }.issubset(pipeline_columns)
    heartbeat_columns = {
        column["name"] for column in inspector.get_columns("worker_heartbeats", schema="reporting")
    }
    assert {"last_progress_at", "orchestrator_healthy"}.issubset(heartbeat_columns)
    attempt_indexes = {
        index["name"]
        for index in inspector.get_indexes("pipeline_run_attempts", schema="reporting")
    }
    assert {
        "ix_pipeline_run_attempts_started_at_desc",
        "uq_pipeline_run_attempts_run_attempt",
    }.issubset(attempt_indexes)
    hourly_indexes = {
        index["name"]
        for index in inspector.get_indexes("hourly_activity_rollups", schema="reporting")
    }
    assert "ix_hourly_rollups_week_range" in hourly_indexes
    with Session(engine) as session:
        rows = list(session.exec(sa_select(SourceLedgerState)).all())
        assert len(rows) == 1
        assert rows[0][0].id == 1
        rollup_rows = list(session.exec(sa_select(RollupState)).all())
        assert len(rollup_rows) == 1
        assert rollup_rows[0][0].id == 1


def test_hourly_rollup_enforces_canonical_key_fk_and_counts(
    engine: Engine,
    inventory_client: Client,
) -> None:
    bucket = datetime(2026, 7, 13, 12, tzinfo=UTC)
    valid = HourlyActivityRollup(
        bucket_start=bucket,
        warehouse="LA",
        client_id=inventory_client.id,
        inbound_movement_count=1,
        inbound_units=5,
        dispatch_order_count=1,
        dispatch_units=3,
        loss_movement_count=1,
        loss_units=2,
        stockout_count=0,
        discrepancy_count=1,
        source_cutoff_at=bucket.replace(hour=13),
        pipeline_version="test",
    )
    valid_values = valid.model_dump()
    with Session(engine) as session:
        session.add(valid)
        session.commit()
        invalid_rows = (
            HourlyActivityRollup(
                **{
                    **valid_values,
                    "bucket_start": bucket.replace(minute=1),
                }
            ),
            HourlyActivityRollup(
                **{
                    **valid_values,
                    "bucket_start": bucket.replace(hour=14),
                    "warehouse": "los_angeles",
                }
            ),
            HourlyActivityRollup(
                **{
                    **valid_values,
                    "bucket_start": bucket.replace(hour=15),
                    "client_id": uuid4(),
                }
            ),
        )
        for row in invalid_rows:
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()


def test_weekly_report_enforces_cross_schema_fk_idempotency_and_kpi_checks(
    engine: Engine,
    inventory_client: Client,
) -> None:
    with Session(engine) as session:
        session.add(_weekly_row(inventory_client.id))
        session.commit()

        invalid_rows = (
            _weekly_row(inventory_client.id),
            _weekly_row(uuid4(), week_start=date(2026, 7, 20)),
            _weekly_row(inventory_client.id, week_start=date(2026, 7, 14)),
            _weekly_row(inventory_client.id, week_start=date(2026, 7, 20), warehouse="unknown"),
            _weekly_row(inventory_client.id, week_start=date(2026, 7, 20), inbound_units_count=-1),
            _weekly_row(inventory_client.id, week_start=date(2026, 7, 20), discrepancy_rate=Decimal("1.1")),
        )
        for row in invalid_rows:
            session.add(row)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        client = session.get(Client, inventory_client.id)
        assert client is not None
        session.delete(client)
        with pytest.raises(IntegrityError):
            session.commit()


def test_reset_and_incomplete_week_constraints(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(SourceLedgerState(id=2))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(IncompleteWeek(week_start=date(2026, 7, 14), reason="ledger_reset"))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(IncompleteWeek(week_start=MONDAY, reason="ledger_reset"))
        session.commit()


def test_pipeline_run_partial_unique_indexes_and_checks(engine: Engine) -> None:
    with Session(engine) as session:
        session.add(
            _run(
                trigger_type="scheduled",
                requested_by="system",
                scheduled_business_date=date(2026, 7, 14),
            )
        )
        session.commit()
        session.add(
            _run(
                trigger_type="scheduled",
                requested_by="system",
                scheduled_business_date=date(2026, 7, 14),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(_run(status="running"))
        session.commit()
        session.add(_run(status="running", cache_nonce=uuid4()))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        # Requested manual rows coalesce by pipeline/week unless force-refresh
        # supplies a nonce, which deliberately represents distinct queued work.
        session.add(_run(requested_week_start=MONDAY))
        session.commit()
        session.add(_run(requested_week_start=MONDAY))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        session.add(_run(requested_week_start=MONDAY, cache_nonce=uuid4()))
        session.commit()

        for invalid in (
            _run(trigger_type="other", cache_nonce=uuid4()),
            _run(status="other", cache_nonce=uuid4()),
            _run(attempt=-1, cache_nonce=uuid4()),
            _run(rows_loaded=-1, cache_nonce=uuid4()),
            _run(error_code="SECRET_INTERNAL_DETAIL", cache_nonce=uuid4()),
        ):
            session.add(invalid)
            with pytest.raises(IntegrityError):
                session.commit()
            session.rollback()

        assert int(session.scalar(sa_select(func.count()).select_from(PipelineRun)) or 0) == 4
