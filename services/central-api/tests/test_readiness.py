"""Readiness rejects stale workers, schema drift, and missing runtime grants."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.db.session import get_session


def _heartbeat(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.worker_heartbeats "
                "(worker_name, heartbeat_at, last_progress_at, orchestrator_healthy) "
                "VALUES ('reporting', now(), now(), true) ON CONFLICT (worker_name) "
                "DO UPDATE SET heartbeat_at = EXCLUDED.heartbeat_at, "
                "last_progress_at = EXCLUDED.last_progress_at, orchestrator_healthy = true"
            )
        )


def test_readiness_rejects_unknown_and_stale_worker(client: TestClient, engine: Engine) -> None:
    assert client.get("/health/ready").status_code == 503
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.worker_heartbeats (worker_name, heartbeat_at) "
                "VALUES ('reporting', now() - interval '31 seconds')"
            )
        )
    assert client.get("/health/ready").status_code == 503


def test_readiness_rejects_older_database_revision(client: TestClient, engine: Engine) -> None:
    _heartbeat(engine)
    with engine.begin() as connection:
        current = str(connection.scalar(text("SELECT version_num FROM alembic_version")))
        connection.execute(text("UPDATE alembic_version SET version_num = '20260714_0008'"))
    try:
        assert client.get("/health/ready").status_code == 503
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE alembic_version SET version_num = :revision"),
                {"revision": current},
            )


def test_readiness_rejects_missing_inventory_column(client: TestClient, engine: Engine) -> None:
    _heartbeat(engine)
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE skus RENAME COLUMN client_id TO client_id_drifted"))
    try:
        assert client.get("/health/ready").status_code == 503
    finally:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE skus RENAME COLUMN client_id_drifted TO client_id"))


def test_readiness_rejects_role_without_reporting_grants(app: FastAPI, engine: Engine) -> None:
    _heartbeat(engine)
    with engine.begin() as connection:
        connection.execute(text("DROP ROLE IF EXISTS readiness_no_access"))
        connection.execute(text("CREATE ROLE readiness_no_access"))

    def restricted_session() -> Generator[Session, None, None]:
        with Session(engine) as session:
            session.execute(text("SET ROLE readiness_no_access"))
            yield session

    app.dependency_overrides[get_session] = restricted_session
    try:
        with TestClient(app) as test_client:
            assert test_client.get("/health/ready").status_code == 503
    finally:
        app.dependency_overrides.pop(get_session, None)
        with engine.begin() as connection:
            connection.execute(text("DROP ROLE IF EXISTS readiness_no_access"))


def test_readiness_rejects_unhealthy_orchestrator_and_stale_poll_progress(
    client: TestClient,
    engine: Engine,
) -> None:
    _heartbeat(engine)
    with engine.begin() as connection:
        connection.execute(text("UPDATE reporting.worker_heartbeats SET orchestrator_healthy = false"))
    assert client.get("/health/ready").status_code == 503
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE reporting.worker_heartbeats SET orchestrator_healthy = true, "
                "last_progress_at = now() - interval '121 seconds'"
            )
        )
    assert client.get("/health/ready").status_code == 503


def test_readiness_uses_stage_deadline_not_renewed_lease(client: TestClient, engine: Engine) -> None:
    _heartbeat(engine)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO reporting.pipeline_runs "
                "(pipeline_name, trigger_type, requested_by, status, attempt, current_stage, "
                "stage_started_at, heartbeat_at, lease_expires_at) "
                "VALUES ('business_performance', 'cli', 'cli', 'running', 1, 'extract', "
                "now() - interval '301 seconds', now(), now() + interval '10 minutes')"
            )
        )
    assert client.get("/health/ready").status_code == 503
