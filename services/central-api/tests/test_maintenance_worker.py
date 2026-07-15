"""Declarative maintenance-worker schedule and shutdown tests."""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Event

import pytest

from scripts import maintenance_worker


def test_daily_prune_boundary_and_guard_interval() -> None:
    schedule = maintenance_worker.MaintenanceSchedule()
    before = datetime(2026, 7, 15, 7, 14, 59, tzinfo=UTC)
    boundary = datetime(2026, 7, 15, 7, 15, tzinfo=UTC)

    assert schedule.tick(now=before, monotonic_now=100.0) == (True, False)
    assert schedule.tick(now=boundary, monotonic_now=101.0) == (False, True)
    assert schedule.tick(now=boundary, monotonic_now=102.0) == (False, False)
    assert schedule.tick(
        now=datetime(2026, 7, 16, 7, 15, tzinfo=UTC),
        monotonic_now=100.0 + maintenance_worker.GUARD_INTERVAL_SECONDS,
    ) == (True, True)


def test_worker_runs_guard_and_both_prunes(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = Event()
    calls: list[str] = []

    class DueSchedule:
        def tick(self, **_kwargs: object) -> tuple[bool, bool]:
            return True, True

    monkeypatch.setattr(maintenance_worker, "guard_once", lambda: calls.append("guard"))
    monkeypatch.setattr(
        maintenance_worker,
        "prune_telemetry_events",
        lambda: calls.append("telemetry") or {"operational": 1, "security": 2},
    )

    def prune_business() -> dict[str, int]:
        calls.append("business")
        stop.set()
        return {"inventory_discrepancies": 3, "stockout_events": 4}

    monkeypatch.setattr(maintenance_worker, "prune_business_events", prune_business)
    maintenance_worker.run_worker(stop=stop, schedule=DueSchedule(), tick_seconds=0.01)  # type: ignore[arg-type]
    assert calls == ["guard", "telemetry", "business"]


def test_signal_handler_requests_shutdown() -> None:
    stop = Event()
    maintenance_worker._stop(stop)(15, None)
    assert stop.is_set()


def test_failed_daily_prune_is_due_again(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = Event()
    calls = 0

    class RetrySchedule:
        last_prune_date = None

        def tick(self, **_kwargs: object) -> tuple[bool, bool]:
            return False, True

    schedule = RetrySchedule()

    def fail_prune() -> dict[str, int]:
        nonlocal calls
        calls += 1
        if calls == 2:
            stop.set()
        raise RuntimeError("private diagnostic")

    monkeypatch.setattr(maintenance_worker, "prune_telemetry_events", fail_prune)
    maintenance_worker.run_worker(stop=stop, schedule=schedule, tick_seconds=0.001)  # type: ignore[arg-type]
    assert calls == 2
    assert schedule.last_prune_date is None
