"""Disposable PostgreSQL fixtures for data-pipeline integration tests."""

from __future__ import annotations

import os
from collections.abc import Generator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url

# The real tests live in the category subfolders (business_performance/, sales_forecasting/, rag/).
# The milestone/graded root shims (test_pipeline.py, test_sales_forecasting.py, test_rag.py) re-export
# them so evaluator commands that name a shim explicitly still work. Ignore the shims during recursive
# directory collection so a bare `pytest tests/pipelines` collects each real test exactly once (no
# import-file-mismatch, no double-run). Explicitly naming a shim on the command line still collects it.
collect_ignore = ["test_pipeline.py", "test_sales_forecasting.py", "test_rag.py"]


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
                "TRUNCATE inventory_discrepancies, stockout_events, stock_exits, stock_entries, stock_balances, stock_ledger_checkpoints, "
                "skus, clients, reporting.weekly_warehouse_client_performance, "
                "reporting.hourly_activity_rollups, reporting.rollup_state, "
                "reporting.pipeline_runs, reporting.incomplete_weeks, "
                "reporting.source_ledger_state, reporting.worker_heartbeats "
                "RESTART IDENTITY CASCADE"
            )
        )
        connection.execute(
            text("INSERT INTO reporting.source_ledger_state (id, updated_at) VALUES (1, now())")
        )
        connection.execute(text("INSERT INTO reporting.rollup_state (id) VALUES (1)"))
    yield
