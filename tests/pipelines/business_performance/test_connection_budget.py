"""Reporting control tasks retain capacity alongside the dedicated publication lock."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import time
from unittest.mock import MagicMock

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout

from pipelines.business_performance.locks import advisory_lock
from pipelines.business_performance.queue import QueueConfigurationError, engine_from_environment
from pipelines.business_performance.queue import RunMetrics, enqueue_cli
from pipelines.business_performance import runner, worker
from pipelines.database import acquire_session_lock, release_session_lock, session_lock_owner


def test_reporting_lock_is_not_an_open_transaction_and_releases_on_failure(pipeline_engine: Engine) -> None:
    key = 999_010_112
    with pytest.raises(RuntimeError, match="injected"), advisory_lock(pipeline_engine, key) as acquired:
        assert acquired
        with pipeline_engine.connect() as observer:
            assert observer.scalar(text(
                "SELECT count(*) FROM pg_locks l JOIN pg_stat_activity a ON a.pid=l.pid "
                "WHERE l.locktype='advisory' AND l.objid=:key AND l.granted AND a.state='idle' AND a.xact_start IS NULL"
            ), {"key": key}) == 1
        raise RuntimeError("injected")
    with advisory_lock(pipeline_engine, key) as acquired:
        assert acquired


@pytest.mark.parametrize("name,value", [
    ("DATABASE_POOL_SIZE", "0"), ("DATABASE_MAX_OVERFLOW", "-1"),
    ("DATABASE_POOL_TIMEOUT_SECONDS", "nan"), ("DATABASE_POOL_SIZE", "not-a-number"),
    ("DATABASE_POOL_SIZE", "15"),
])
def test_reporting_rejects_invalid_pool_settings(monkeypatch: pytest.MonkeyPatch, name: str, value: str) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(QueueConfigurationError, match="Invalid database pool limits"):
        engine_from_environment()


def test_reporting_pool_supports_five_simultaneous_consumers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_POOL_SIZE", "2")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "3")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "0.5")
    engine = engine_from_environment()
    ready = Barrier(5)
    def use_slot() -> int:
        with engine.connect() as connection:
            ready.wait(timeout=3)
            return int(connection.scalar(text("SELECT 1")))
    try:
        with advisory_lock(engine, 999_010_113) as acquired:
            assert acquired
            with ThreadPoolExecutor(max_workers=4) as threads:
                futures = [threads.submit(use_slot) for _ in range(4)]
                ready.wait(timeout=3)
                assert [future.result(timeout=3) for future in futures] == [1] * 4
    finally:
        engine.dispose()


def test_uncertain_lock_cleanup_invalidates_session_without_logging_driver_payload(
    caplog: pytest.LogCaptureFixture,
) -> None:
    connection = MagicMock(closed=False, invalidated=False)
    connection.scalar.side_effect = OperationalError("private sql", {}, Exception("private dsn"))
    release_session_lock(connection, 123)
    connection.invalidate.assert_called_once()
    assert "database_lock_cleanup_failed error_type=OperationalError" in caplog.text
    assert "private" not in caplog.text


def test_invalidated_lock_owner_is_not_reconnected() -> None:
    connection = MagicMock(closed=False, invalidated=True)
    assert session_lock_owner(connection, 123) is None
    connection.scalar.assert_not_called()


def test_uncertain_acquisition_and_owner_probe_invalidate_connection() -> None:
    for operation in (acquire_session_lock, session_lock_owner):
        connection = MagicMock(closed=False, invalidated=False)
        connection.scalar.side_effect = OperationalError("private sql", {}, Exception("private dsn"))
        with pytest.raises(OperationalError):
            operation(connection, 123)
        connection.invalidate.assert_called_once()


def test_reporting_exhaustion_has_bounded_checkout_and_safe_diagnostic(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DATABASE_POOL_SIZE", "1")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "0")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "0.05")
    engine = engine_from_environment()
    try:
        with engine.connect(), pytest.raises(PoolTimeout):
            engine.connect()
        assert "database_pool_exhausted service=reporting-worker" in caplog.text
        assert "postgresql" not in caplog.text
    finally:
        engine.dispose()


def test_capped_worker_renews_while_executor_and_control_tasks_overlap(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("DATABASE_POOL_SIZE", "2")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "3")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "0.5")
    monkeypatch.setenv("REPORTING_HEARTBEAT_SECONDS", "0.01")
    engine = engine_from_environment()
    stop = Event()
    renewals = []
    original = runner.heartbeat

    def observe_renewal(*args: object, **kwargs: object) -> bool:
        renewed = original(*args, **kwargs)
        renewals.append(renewed)
        return renewed

    monkeypatch.setattr(runner, "heartbeat", observe_renewal)

    def occupied_executor(_engine: Engine, _claim: object, _abort: Event) -> RunMetrics:
        # The singleton lock and an executor slot remain borrowed while real lease,
        # heartbeat and dispatcher SQL compete for the other three slots.
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as compute:
            assert compute.scalar(text("SELECT 1")) == 1
            time.sleep(0.15)
        stop.set()
        return RunMetrics(0, 0, 0)

    try:
        run_id = enqueue_cli(engine)
        worker.run_worker(
            engine, occupied_executor, stop=stop, poll_interval_seconds=0.001,
            heartbeat_interval_seconds=0.01, dispatch_interval_seconds=0.01,
        )
        assert len(renewals) >= 3 and all(renewals)
        with engine.connect() as observer:
            assert observer.scalar(text("SELECT status FROM reporting.pipeline_runs WHERE id=:id"), {"id": run_id}) == "succeeded"
            assert observer.scalar(text("SELECT count(*) FROM reporting.worker_heartbeats")) == 1
        assert "reporting_worker_operation_failed" not in caplog.text
        assert "database_pool_exhausted" not in caplog.text
    finally:
        engine.dispose()
