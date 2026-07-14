"""Disposable PostgreSQL fixtures for data-pipeline integration tests."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url


@pytest.fixture(scope="session")
def database_url() -> str:
    raw_url = os.environ.get("DATABASE_URL", "").strip()
    if not raw_url:
        pytest.fail("DATABASE_URL is required for the pipeline queue integration tests")
    parsed = make_url(raw_url)
    if parsed.host not in {"127.0.0.1", "localhost"} or parsed.port != 55432:
        pytest.fail("Pipeline tests require the disposable local PostgreSQL on port 55432")
    return parsed.set(drivername="postgresql+psycopg").render_as_string(hide_password=False)


@pytest.fixture(scope="session")
def pipeline_engine(database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(database_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_pipeline_tables(pipeline_engine: Engine) -> Generator[None, None, None]:
    with pipeline_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE reporting.weekly_warehouse_client_performance, "
                "reporting.pipeline_runs, reporting.incomplete_weeks, "
                "reporting.source_ledger_state RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(
            text("INSERT INTO reporting.source_ledger_state (id, updated_at) VALUES (1, now())")
        )
    yield
