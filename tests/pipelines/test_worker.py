"""Long-running reporting worker scheduling and shutdown proofs."""

from __future__ import annotations

import logging
from threading import Event, Thread
from typing import Any

import pytest

from pipelines.business_performance import worker
from pipelines.business_performance.runner import RunnerResult, RunnerStatus


def test_worker_heartbeats_dispatches_polls_and_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    stop = Event()
    calls = {"heartbeat": 0, "dispatch": 0, "poll": 0}

    def count(name: str) -> None:
        calls[name] += 1

    monkeypatch.setattr(worker, "record_worker_heartbeat", lambda _engine: count("heartbeat"))
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: count("dispatch"))

    def poll(_engine: Any, _executor: Any) -> RunnerResult:
        count("poll")
        if all(calls.values()):
            stop.set()
        return RunnerResult(RunnerStatus.IDLE)

    monkeypatch.setattr(worker, "run_once", poll)
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


def test_worker_logs_only_safe_exception_type(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
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
