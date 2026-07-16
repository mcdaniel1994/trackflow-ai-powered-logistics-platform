"""Post-deployment proof that the new reporting worker cleared its startup guard.

The previous worker heartbeats until the instant Compose replaces it, so
freshness alone cannot distinguish "the new worker is healthy" from "the old
worker was healthy moments before deploy". Only a heartbeat at or after the
deployment boundary proves the new container reached its poll loop.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from scripts.verify_reporting_startup import evaluate_heartbeat, verify

BOUNDARY = datetime(2026, 7, 15, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def clean_database() -> None:
    """Override the package-wide database fixture: these are pure unit tests."""
    return None


def _worker(*, heartbeat_at: datetime | None, orchestrator_healthy: bool | None = True):
    return {"heartbeat_at": heartbeat_at, "orchestrator_healthy": orchestrator_healthy}


def test_accepts_a_heartbeat_written_after_the_deployment_boundary() -> None:
    worker = _worker(heartbeat_at=BOUNDARY + timedelta(seconds=30))
    assert evaluate_heartbeat(worker, boundary=BOUNDARY) is None


def test_accepts_a_heartbeat_exactly_on_the_boundary() -> None:
    assert evaluate_heartbeat(_worker(heartbeat_at=BOUNDARY), boundary=BOUNDARY) is None


def test_rejects_a_recent_heartbeat_that_predates_the_deployment() -> None:
    """The regression this exists for: fresh, but written by the previous worker.

    60s old would pass any "younger than 180s" freshness window, yet it proves
    nothing about the worker the deployment just started.
    """
    worker = _worker(heartbeat_at=BOUNDARY - timedelta(seconds=60))
    assert evaluate_heartbeat(worker, boundary=BOUNDARY) == "worker_heartbeat_predates_deployment"


def test_rejects_a_heartbeat_from_well_before_the_deployment() -> None:
    worker = _worker(heartbeat_at=BOUNDARY - timedelta(hours=3))
    assert evaluate_heartbeat(worker, boundary=BOUNDARY) == "worker_heartbeat_predates_deployment"


def test_rejects_an_absent_worker_row() -> None:
    assert evaluate_heartbeat(None, boundary=BOUNDARY) == "worker_heartbeat_absent"


def test_rejects_a_null_heartbeat() -> None:
    assert evaluate_heartbeat(_worker(heartbeat_at=None), boundary=BOUNDARY) == "worker_heartbeat_absent"


@pytest.mark.parametrize("healthy", [False, None])
def test_rejects_an_unhealthy_orchestrator_even_past_the_boundary(healthy: bool | None) -> None:
    worker = _worker(heartbeat_at=BOUNDARY + timedelta(seconds=30), orchestrator_healthy=healthy)
    assert evaluate_heartbeat(worker, boundary=BOUNDARY) == "orchestrator_unhealthy"


def test_polls_until_the_new_worker_heartbeats_past_the_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    """The new worker needs a heartbeat interval or two after the deploy returns."""
    import scripts.verify_reporting_startup as module

    rows = [
        _worker(heartbeat_at=BOUNDARY - timedelta(seconds=10)),  # previous worker
        None,  # replaced, not yet heartbeating
        _worker(heartbeat_at=BOUNDARY + timedelta(seconds=5)),  # new worker proved itself
    ]
    monkeypatch.setattr(module, "create_engine", lambda *a, **k: _FakeEngine())
    monkeypatch.setattr(module, "_read_heartbeat", lambda _engine: rows.pop(0))
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/x")
    assert verify(boundary=BOUNDARY, timeout_seconds=60, interval_seconds=0, sleep=lambda _s: None) is None


def test_gives_up_at_the_deadline_with_the_last_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    import scripts.verify_reporting_startup as module

    monkeypatch.setattr(module, "create_engine", lambda *a, **k: _FakeEngine())
    monkeypatch.setattr(
        module, "_read_heartbeat", lambda _engine: _worker(heartbeat_at=BOUNDARY - timedelta(seconds=10))
    )
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/x")
    clock = iter([0.0, 1.0, 99.0, 99.0])
    reason = verify(
        boundary=BOUNDARY,
        timeout_seconds=10,
        interval_seconds=0,
        monotonic=lambda: next(clock),
        sleep=lambda _s: None,
    )
    assert reason == "worker_heartbeat_predates_deployment"


class _FakeEngine:
    def dispose(self) -> None:
        return None
