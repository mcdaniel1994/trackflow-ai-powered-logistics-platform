"""Opt-in ten-minute acceptance workload; the shared fixture refuses remote databases."""

import logging
import os
import time
from collections.abc import Callable, Generator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Event, Thread

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pipelines.business_performance.direct_executor import direct_sql_executor
from pipelines.business_performance.queue import engine_from_environment, enqueue_cli
from pipelines.business_performance.worker import run_worker as reporting_worker
from pipelines.database import acquire_session_lock, release_session_lock, session_lock_owner
from sqlalchemy import Engine, text
from sqlmodel import Session

from central_api.core.config import Settings
from central_api.db import session as database
from central_api.db.session import get_session
from central_api.domains.rfp import checkpointer as cp
from central_api.domains.telemetry import recorder
from scripts import db_size_guard, maintenance_worker, operations_feed, reconcile_stock_balances

SOAK_SECONDS = int(os.environ.get("TRACKFLOW_CONNECTION_SOAK_SECONDS", "0"))
ACTOR = "11111111-1111-4111-8111-111111111111"


@pytest.mark.skipif(SOAK_SECONDS < 600, reason="Set TRACKFLOW_CONNECTION_SOAK_SECONDS=600 for acceptance")
def test_combined_runtime_connection_budget(
    app: FastAPI, settings: Settings, engine: Engine, auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    """Two dashboard request clients run beside real feed/reporting/maintenance code."""
    caplog.set_level(logging.ERROR)
    stop = Event()
    errors: list[tuple[str, str]] = []
    peak = 0
    samples = 0
    cfg = settings.model_copy(update={"telemetry_enabled": True})

    def make_engine(service: str, size: int, overflow: int) -> Engine:
        service_cfg = cfg.model_copy(update={
            "database_service_name": service, "database_pool_size": size, "database_max_overflow": overflow,
        })
        return database.create_runtime_engine(service_cfg)

    api = make_engine("central-api", 3, 0)
    feed = make_engine("operations-feed", 2, 1)
    maintenance = make_engine("maintenance-worker", 1, 0)
    monkeypatch.setenv("DATABASE_POOL_SIZE", "2")
    monkeypatch.setenv("DATABASE_MAX_OVERFLOW", "3")
    monkeypatch.setenv("DATABASE_POOL_TIMEOUT_SECONDS", "5")
    monkeypatch.setenv("REPORTING_HEARTBEAT_SECONDS", "1")
    monkeypatch.setenv("REPORTING_HOURLY_ROLLUPS_ENABLED", "true")
    reporting = engine_from_environment()
    monkeypatch.setattr(database, "get_settings", lambda: cfg)
    monkeypatch.setattr(recorder, "get_settings", lambda: cfg)
    monkeypatch.setattr(recorder, "get_engine", lambda: feed)
    monkeypatch.setattr(db_size_guard, "get_engine", lambda: maintenance)
    monkeypatch.setattr(reconcile_stock_balances, "get_engine", lambda: maintenance)

    def api_session() -> Generator[Session, None, None]:
        with Session(api) as session:
            yield session
    app.dependency_overrides[get_session] = api_session

    with Session(feed) as session:
        operations_feed.ensure_baseline(session, ACTOR)
        operations_feed.backfill_history(session, ACTOR, days=2)

    def guarded(role: str, operation: Callable[[], None]) -> None:
        try:
            operation()
        except BaseException as exc:
            errors.append((role, type(exc).__name__))
            stop.set()

    def feed_loop() -> None:
        key = cfg.operations_feed_lock_key
        with feed.connect().execution_options(isolation_level="AUTOCOMMIT") as connection:
            assert acquire_session_lock(connection, key)
            owner = session_lock_owner(connection, key)
            try:
                while not stop.is_set():
                    operations_feed.require_singleton_lock(connection, key, owner)
                    with Session(feed) as session:
                        operations_feed.run_tick(session, ACTOR, cfg)
                    stop.wait(1)
            finally:
                release_session_lock(connection, key)

    class Schedule(maintenance_worker.MaintenanceSchedule):
        def tick(self, *, now: datetime, monotonic_now: float) -> tuple[bool, bool]:
            due = monotonic_now >= self.next_guard_at
            if due:
                self.next_guard_at = monotonic_now + 30
            return due, False

    today = datetime.now(UTC).date().isoformat()
    paths = [
        f"/telemetry/metrics/{metric}?from={today}&to={today}"
        for metric in ("dispatch", "receiving", "stock-loss")
    ] + ["/inventory/orders?limit=8&offset=0"]

    def dashboard(client: TestClient) -> None:
        with ThreadPoolExecutor(max_workers=4) as requests:
            while not stop.is_set():
                responses = list(requests.map(lambda path: client.get(path, headers=auth_headers), paths))
                assert all(response.status_code == 200 for response in responses)
                stop.wait(20)

    def checkpoints() -> None:
        while not stop.is_set():
            with cp.approval_checkpointer(cfg) as saver:
                saver.get_tuple({"configurable": {"thread_id": "connection-budget-fixture"}})
            stop.wait(1)

    operations: list[tuple[str, Callable[[], None]]] = [
        ("feed", feed_loop),
        ("reporting", lambda: reporting_worker(
            reporting, direct_sql_executor, stop=stop, poll_interval_seconds=0.25,
            heartbeat_interval_seconds=1, dispatch_interval_seconds=5,
        )),
        ("maintenance", lambda: maintenance_worker.run_worker(stop=stop, schedule=Schedule(), tick_seconds=1)),
        ("checkpoints", checkpoints),
    ]
    threads: list[Thread] = []
    try:
        with TestClient(app) as first, TestClient(app) as second:
            operations.extend([("dashboard-1", lambda: dashboard(first)), ("dashboard-2", lambda: dashboard(second))])
            for role, operation in operations:
                thread = Thread(target=guarded, args=(role, operation), daemon=True)
                thread.start()
                threads.append(thread)
            deadline = time.monotonic() + SOAK_SECONDS
            next_report = 0.0
            while time.monotonic() < deadline and not stop.is_set():
                if time.monotonic() >= next_report:
                    enqueue_cli(reporting)
                    next_report = time.monotonic() + 30
                with engine.connect() as observer:
                    counts = observer.execute(text(
                        "SELECT count(*), count(*) FILTER (WHERE state='idle in transaction' "
                        "AND EXISTS (SELECT 1 FROM pg_locks l WHERE l.pid=a.pid AND l.locktype='advisory')) "
                        "FROM pg_stat_activity a WHERE application_name LIKE 'trackflow:%'"
                    )).one()
                peak = max(peak, counts[0])
                samples += 1
                assert counts[0] <= 13 and counts[1] == 0
                stop.wait(0.25)
            stop.set()
            for thread in threads:
                thread.join(timeout=20)
                assert not thread.is_alive()
            assert not errors, errors
            assert "database_pool_exhausted" not in caplog.text
            assert "reporting_worker_operation_failed" not in caplog.text
            assert "maintenance_operation_failed" not in caplog.text
            with engine.connect() as observer:
                succeeded = observer.scalar(
                    text("SELECT count(*) FROM reporting.pipeline_runs WHERE status='succeeded'")
                )
                assert succeeded > 0
                assert observer.scalar(text("SELECT count(*) FROM reporting.pipeline_runs WHERE status='failed'")) == 0
            print(
                f"connection_workload seconds={SOAK_SECONDS} samples={samples} "
                f"peak_runtime_connections={peak} errors=0"
            )
    finally:
        stop.set()
        for thread in threads:
            thread.join(timeout=20)
        cp.close_checkpoint_pool()
        for pool_engine in (api, feed, reporting, maintenance):
            pool_engine.dispose()
