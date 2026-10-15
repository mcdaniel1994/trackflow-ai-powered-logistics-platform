"""Connection budgets, checkout backpressure, checkpoint borrowing and safe failures."""

import logging
import time
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout
from pydantic import ValidationError
from sqlalchemy import Engine, text
from sqlalchemy.exc import TimeoutError as SQLPoolTimeout
from sqlmodel import Session

from central_api.core.config import Settings
from central_api.db import session as database
from central_api.db.session import get_session
from central_api.domains.rfp import checkpointer as cp


@pytest.fixture
def bounded_engine(settings: Settings, monkeypatch: pytest.MonkeyPatch) -> Generator[Engine, None, None]:
    cfg = settings.model_copy(update={"database_pool_timeout_seconds": 0.1})
    database.dispose_engine()
    monkeypatch.setattr(database, "get_settings", lambda: cfg)
    engine = database.get_engine()
    yield engine
    engine.dispose()
    database.dispose_engine()


@pytest.mark.parametrize("fields", [
    {"database_pool_size": 0}, {"database_max_overflow": -1},
    {"database_pool_timeout_seconds": 0}, {"database_pool_timeout_seconds": float("inf")},
    {"database_pool_size": 15, "database_max_overflow": 1},
])
def test_rejects_unbounded_or_invalid_pool_settings(settings: Settings, fields: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        Settings(**{**settings.model_dump(), **fields})


def test_api_checkout_limit_is_bounded_and_does_not_log_secrets(
    bounded_engine: Engine, caplog: pytest.LogCaptureFixture,
) -> None:
    with bounded_engine.connect() as first, bounded_engine.connect(), bounded_engine.connect():
        assert first.scalar(text("SHOW application_name")) == "trackflow:central-api"
        started = time.monotonic()
        with caplog.at_level(logging.ERROR), pytest.raises(SQLPoolTimeout):
            bounded_engine.connect()
        assert time.monotonic() - started < 1
        assert "database_pool_exhausted service=central-api" in caplog.text
        assert "checked_out=3" in caplog.text
        assert "postgresql" not in caplog.text
    with bounded_engine.connect() as recovered:
        assert recovered.scalar(text("SELECT 1")) == 1


def test_saturated_authenticated_api_returns_safe_503(
    app: FastAPI, client: TestClient, auth_headers: dict[str, str], bounded_engine: Engine,
) -> None:
    def unit_of_work() -> Generator[Session, None, None]:
        with Session(bounded_engine) as session:
            yield session

    app.dependency_overrides[get_session] = unit_of_work
    with bounded_engine.connect(), bounded_engine.connect(), bounded_engine.connect():
        response = client.get("/telemetry/metrics/receiving?from=2026-10-09&to=2026-10-15", headers=auth_headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Telemetry service temporarily unavailable"}


def test_checkpoint_graph_context_borrows_instead_of_holding_a_connection(settings: Settings) -> None:
    with cp.approval_checkpointer(settings) as saver:
        assert cp._tables_present(saver)
        pool = cp.checkpoint_pool(settings)
        assert pool.max_size == 1 and pool.min_size == 0
        # The graph context is still open; another checkpoint operation can use the slot.
        with pool.connection(timeout=0.2) as connection:
            assert connection.autocommit
            name = connection.execute("SHOW application_name").fetchone()["application_name"]
            assert name == "trackflow:rfp-checkpoints"
            with ThreadPoolExecutor(max_workers=1) as executor:
                pending = executor.submit(lambda: _checkout_checkpoint(pool))
                with pytest.raises(PoolTimeout):
                    pending.result(timeout=1)
        with pool.connection(timeout=0.2) as recovered:
            assert recovered.execute("SELECT 1 AS value").fetchone()["value"] == 1
    cp.close_checkpoint_pool()
    assert pool.closed


def _checkout_checkpoint(pool: object) -> None:
    with pool.connection(timeout=0.1):  # type: ignore[attr-defined]
        pass


def test_checkpoint_errors_are_safe_503(app: FastAPI, client: TestClient) -> None:
    @app.get("/_test_checkpoint_timeout")
    def unavailable() -> None:
        raise PoolTimeout("private connection string and driver message")

    response = client.get("/_test_checkpoint_timeout")
    assert response.status_code == 503
    assert response.json() == {"detail": "RFP service temporarily unavailable"}


def test_pool_reconnect_logs_do_not_expose_driver_messages(caplog: pytest.LogCaptureFixture) -> None:
    logging.getLogger("psycopg.pool").warning("private DSN sentinel: %s", "private payload sentinel")
    assert "checkpoint_pool_connection_event" in caplog.text
    assert "sentinel" not in caplog.text


def test_simultaneous_first_requests_share_one_engine(
    settings: Settings, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from threading import Barrier

    database.dispose_engine()
    monkeypatch.setattr(database, "get_settings", lambda: settings)
    factory = database.create_engine
    constructions = []
    def slow_factory(*args: object, **kwargs: object) -> Engine:
        time.sleep(0.02)  # Make the cold-start cache race reproducible.
        created = factory(*args, **kwargs)
        constructions.append(created)
        return created
    monkeypatch.setattr(database, "create_engine", slow_factory)
    ready = Barrier(8)
    def first_request() -> Engine:
        ready.wait(timeout=2)
        return database.get_engine()
    try:
        with ThreadPoolExecutor(max_workers=8) as requests:
            engines = list(requests.map(lambda _: first_request(), range(8)))
        assert len(constructions) == 1
        assert all(engine is engines[0] for engine in engines)
    finally:
        database.dispose_engine()
