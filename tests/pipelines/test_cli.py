"""One-shot CLI and scheduled runner entrypoint behavior."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Any

import pytest

from pipelines import pipeline
from pipelines.business_performance import runner
from pipelines.business_performance.runner import RunnerResult, RunnerStatus


class _Engine:
    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


def test_direct_cli_enqueues_runs_and_disposes(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    requested: list[date | None] = []
    monkeypatch.setattr(pipeline, "engine_from_environment", lambda: engine)
    monkeypatch.setattr(
        pipeline,
        "enqueue_cli",
        lambda _engine, requested_week_start=None: requested.append(requested_week_start),
    )
    monkeypatch.setattr(
        pipeline,
        "run_once",
        lambda _engine, _executor: RunnerResult(RunnerStatus.SUCCEEDED, "run-id"),
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--week-start", "2026-07-13"])
    assert pipeline.main() == 0
    assert requested == [date(2026, 7, 13)]
    assert engine.disposed is True


def test_direct_cli_returns_failure_and_validates_monday(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    monkeypatch.setattr(pipeline, "engine_from_environment", lambda: engine)
    monkeypatch.setattr(pipeline, "enqueue_cli", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        pipeline,
        "run_once",
        lambda _engine, _executor: RunnerResult(RunnerStatus.RETRYABLE, "run-id"),
    )
    monkeypatch.setattr(sys, "argv", ["pipeline.py"])
    assert pipeline.main() == 1
    with pytest.raises(argparse.ArgumentTypeError, match="ISO Monday"):
        pipeline._week_start("2026-07-14")


def test_runner_main_uses_prefect_executor_and_disposes(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _Engine()
    called: list[Any] = []
    monkeypatch.setattr(runner, "engine_from_environment", lambda: engine)
    monkeypatch.setattr(runner, "run_once", lambda used_engine, executor: called.extend([used_engine, executor]))
    runner.main()
    assert called[0] is engine
    assert callable(called[1])
    assert engine.disposed is True
