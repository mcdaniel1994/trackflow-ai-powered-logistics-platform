"""Phase 3 reporting-schema constraints, indexes, and cleanup invariants."""

from datetime import date
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
    IncompleteWeek,
    PipelineRun,
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
        "incomplete_weeks",
        "pipeline_runs",
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
    }.issubset(pipeline_columns)
    with Session(engine) as session:
        rows = list(session.exec(sa_select(SourceLedgerState)).all())
        assert len(rows) == 1
        assert rows[0][0].id == 1


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
