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


def test_steady_state_polling_does_not_write_a_heartbeat_per_poll(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Polling must not write the heartbeat row.

    The per-poll heartbeat write was the single largest source of database write
    volume in production. Only the periodic beat and a genuine orchestrator-health
    transition may write the row.
    """
    stop = Event()
    writes: list[dict[str, object]] = []
    polls = 0

    monkeypatch.setattr(
        worker, "record_worker_heartbeat", lambda _engine, **kwargs: writes.append(kwargs)
    )
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: None)

    def poll(_engine: Any) -> None:
        nonlocal polls
        polls += 1
        if polls >= 25:
            stop.set()
        return None

    monkeypatch.setattr(worker, "claim_next", poll)
    worker.run_worker(
        object(),
        lambda *_args: None,
        stop=stop,
        poll_interval_seconds=0.0,
        # Long enough that no periodic beat fires during the polling burst, so any
        # write observed here came from the poll loop itself.
        heartbeat_interval_seconds=30.0,
        dispatch_interval_seconds=30.0,
    )

    assert polls >= 25
    # At most two writes: the thread's opening beat, and the first health verdict
    # written through as a transition from "unknown". Never one per poll.
    assert len(writes) <= 2, f"{len(writes)} writes for {polls} polls"
    assert any(item.get("orchestrator_healthy") is True for item in writes)


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
    worker._run_watchdog(Event(), 0.001, str(uuid4()), 1)
    assert exits == [1]


def test_worker_kill_switch_keeps_heartbeat_but_skips_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = Event()
    heartbeats = 0
    monkeypatch.setenv("REPORTING_COMPUTATION_ENABLED", "false")
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: None)

    def record(_engine: object, **_kwargs: object) -> None:
        nonlocal heartbeats
        heartbeats += 1
        if heartbeats >= 2:
            stop.set()

    monkeypatch.setattr(worker, "record_worker_heartbeat", record)
    monkeypatch.setattr(
        worker,
        "claim_next",
        lambda _engine: pytest.fail("disabled computation claimed work"),
    )
    worker.run_worker(
        object(),
        lambda *_args: None,
        stop=stop,
        poll_interval_seconds=0.001,
        heartbeat_interval_seconds=0.001,
        dispatch_interval_seconds=0.001,
    )
    assert heartbeats >= 2


def test_worker_drives_explicit_claim_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = Event()
    claim = RunClaim(
        uuid4(), uuid4(), "cli", date(2026, 7, 13), (date(2026, 7, 13),), 1
    )
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


def test_worker_claims_and_finalizes_one_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = Event()
    claim = RunClaim(
        uuid4(), uuid4(), "scheduled", date(2026, 7, 13), (date(2026, 7, 13),), 1
    )
    heartbeats: list[dict[str, object]] = []
    monkeypatch.setattr(worker, "dispatch_tick", lambda _engine: None)
    monkeypatch.setattr(
        worker,
        "record_worker_heartbeat",
        lambda _engine, **kwargs: heartbeats.append(kwargs),
    )
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
    assert any(item.get("orchestrator_healthy") is True for item in heartbeats)
