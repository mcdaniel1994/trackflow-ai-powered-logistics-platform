"""Long-running reporting worker scheduling and shutdown proofs."""

from __future__ import annotations

import logging
from datetime import date
from threading import Event, Thread
from typing import Any
from uuid import uuid4

import pytest

from pipelines.business_performance import worker
from pipelines.business_performance.queue import RunClaim
from pipelines.business_performance.runner import (
    ClaimOutcome,
    RunnerResult,
    RunnerStatus,
)


def test_worker_heartbeats_dispatches_polls_and_stops(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = Event()
    calls = {"heartbeat": 0, "dispatch": 0, "poll": 0}

    def count(name: str) -> None:
        calls[name] += 1

    monkeypatch.setattr(
        worker, "record_worker_heartbeat", lambda _engine, **_kwargs: count("heartbeat")
    )
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: count("dispatch"))
    monkeypatch.setattr(worker, "prefect_is_healthy", lambda: True)
    monkeypatch.setattr(
        "pipelines.business_performance.flows.reconcile_orphaned_flow_runs",
        lambda _engine: 0,
    )

    def poll(_engine: Any) -> None:
        count("poll")
        if all(calls.values()):
            stop.set()
        return None

    monkeypatch.setattr(worker, "claim_next", poll)
    thread = Thread(
        target=worker.run_worker,
        args=(object(), lambda *_args: None),
        kwargs={
            "stop": stop,
            "poll_interval_seconds": 0.01,
            "heartbeat_interval_seconds": 0.01,
            "dispatch_interval_seconds": 0.01,
        },
    )
    thread.start()
    thread.join(timeout=1)
    assert thread.is_alive() is False
    assert calls["heartbeat"] >= 1
    assert calls["dispatch"] >= 1
    assert calls["poll"] >= 1


def test_worker_logs_only_safe_exception_type(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    stop = Event()

    def fail() -> None:
        stop.set()
        raise RuntimeError("postgresql://user:secret@private/report")

    with caplog.at_level(logging.ERROR):
        worker._periodic(
            stop,
            interval_seconds=0.01,
            operation_name="heartbeat",
            operation=fail,
        )
    assert "RuntimeError" in caplog.text
    assert "secret" not in caplog.text
    assert "private" not in caplog.text


def test_signal_handler_requests_shutdown() -> None:
    stop = Event()
    worker._stop(stop)(15, None)
    assert stop.is_set()


def test_watchdog_uses_fixed_log_and_process_exit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exits: list[int] = []
    monkeypatch.setattr(worker.os, "_exit", lambda code: exits.append(code))
    worker._run_watchdog(Event(), 0.001)
    assert exits == [1]


def test_prefect_health_fails_closed_without_api_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PREFECT_API_URL", raising=False)
    assert worker.prefect_is_healthy() is False


def test_prefect_health_accepts_only_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status = 200

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setenv("PREFECT_API_URL", "http://prefect-server:4200/api")
    monkeypatch.setattr(
        worker.urllib.request, "urlopen", lambda *_args, **_kwargs: Response()
    )
    assert worker.prefect_is_healthy() is True


def test_prefect_health_fails_closed_on_transport_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PREFECT_API_URL", "http://prefect-server:4200/api")
    monkeypatch.setattr(
        worker.urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("unavailable")),
    )
    assert worker.prefect_is_healthy() is False


def test_worker_skips_claim_when_prefect_is_unhealthy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = Event()
    heartbeats: list[dict[str, object]] = []
    monkeypatch.setattr(
        "pipelines.business_performance.flows.reconcile_orphaned_flow_runs",
        lambda _engine: 0,
    )
    monkeypatch.setattr(worker, "prefect_is_healthy", lambda: False)
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: None)

    def record(_engine: object, **kwargs: object) -> None:
        heartbeats.append(kwargs)
        if "orchestrator_healthy" in kwargs:
            stop.set()

    monkeypatch.setattr(worker, "record_worker_heartbeat", record)
    monkeypatch.setattr(
        worker,
        "claim_next",
        lambda _engine: pytest.fail("unhealthy worker claimed work"),
    )
    worker.run_worker(
        object(),
        lambda *_args: None,
        stop=stop,
        poll_interval_seconds=0.001,
        heartbeat_interval_seconds=0.001,
        dispatch_interval_seconds=0.001,
    )
    assert any(item.get("orchestrator_healthy") is False for item in heartbeats)


def test_worker_drives_explicit_claim_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = Event()
    claim = RunClaim(
        uuid4(), uuid4(), "cli", date(2026, 7, 13), (date(2026, 7, 13),), 1
    )
    monkeypatch.setattr(
        "pipelines.business_performance.flows.reconcile_orphaned_flow_runs",
        lambda _engine: 0,
    )
    monkeypatch.setattr(worker, "prefect_is_healthy", lambda: True)
    monkeypatch.setattr(
        worker, "record_worker_heartbeat", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: None)
    monkeypatch.setattr(worker, "claim_next", lambda _engine: claim)
    monkeypatch.setattr(
        worker,
        "execute_claim_with_renewal",
        lambda *_args: ClaimOutcome(RunnerStatus.SUCCEEDED),
    )

    def finalize(*_args: object) -> RunnerResult:
        stop.set()
        return RunnerResult(RunnerStatus.SUCCEEDED, str(claim.run_id))

    monkeypatch.setattr(worker, "finalize_claim", finalize)
    worker.run_worker(
        object(),
        lambda *_args: None,
        stop=stop,
        poll_interval_seconds=0.001,
        heartbeat_interval_seconds=0.001,
        dispatch_interval_seconds=0.001,
    )
    assert stop.is_set()
