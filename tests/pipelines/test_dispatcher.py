"""Scheduling proofs for the 07:00 America/Chicago dispatcher."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import Engine, text

from pipelines.business_performance.dispatcher import dallas_business_time, dispatch_tick


@pytest.mark.parametrize(
    ("utc_instant", "expected_offset_hours"),
    [
        (datetime(2026, 1, 15, 13, 0, tzinfo=UTC), -6),
        (datetime(2026, 7, 15, 12, 0, tzinfo=UTC), -5),
    ],
)
def test_cst_and_cdt_trigger_at_seven_local(
    pipeline_engine: Engine,
    utc_instant: datetime,
    expected_offset_hours: int,
) -> None:
    local = dallas_business_time(utc_instant)
    assert local.hour == 7
    assert local.utcoffset() is not None
    assert local.utcoffset().total_seconds() == expected_offset_hours * 3600
    assert dispatch_tick(pipeline_engine, now=utc_instant).scheduled_run_created is True


def test_dispatch_boundary_and_duplicate_ticks(pipeline_engine: Engine) -> None:
    before = datetime(2026, 7, 15, 11, 59, 59, tzinfo=UTC)
    boundary = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    assert dispatch_tick(pipeline_engine, now=before).scheduled_run_created is False
    assert dispatch_tick(pipeline_engine, now=boundary).scheduled_run_created is True
    assert dispatch_tick(pipeline_engine, now=boundary).scheduled_run_created is False

    with pipeline_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT trigger_type, requested_by, scheduled_business_date, status "
                "FROM reporting.pipeline_runs"
            )
        ).mappings().one()
    assert row == {
        "trigger_type": "scheduled",
        "requested_by": "system",
        "scheduled_business_date": date(2026, 7, 15),
        "status": "requested",
    }


def test_first_tick_after_missed_window_recovers_today(pipeline_engine: Engine) -> None:
    recovered = dispatch_tick(
        pipeline_engine,
        now=datetime(2026, 7, 15, 14, 20, tzinfo=UTC),
    )
    assert recovered.business_date == date(2026, 7, 15)
    assert recovered.scheduled_run_created is True


def test_dispatch_clock_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        dallas_business_time(datetime(2026, 7, 15, 7, 0))
