"""Alembic upgrade and rollback checks on an isolated disposable database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from central_api.core.config import get_settings

SERVICE_ROOT = Path(__file__).resolve().parents[1]


def test_migration_upgrade_and_rollback(database_url: str, monkeypatch: object) -> None:
    """Build a fresh database so rollback verification cannot disrupt API tests."""
    migration_database = "trackflow_inventory_migration_test"
    parsed = make_url(database_url)
    admin_engine = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    migration_url = parsed.set(database=migration_database)

    with admin_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{migration_database}" WITH (FORCE)'))
        connection.execute(text(f'CREATE DATABASE "{migration_database}"'))

    try:
        monkeypatch.setenv("DATABASE_URL", migration_url.render_as_string(hide_password=False))  # type: ignore[attr-defined]
        get_settings.cache_clear()
        config = Config(str(SERVICE_ROOT / "alembic.ini"))

        command.upgrade(config, "20260713_0005")
        engine = create_engine(migration_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO skus (name, sku, client_name, category, warehouse) "
                    "VALUES ('Legacy One', 'LEGACY-1', 'Legacy Client', 'fashion', 'LA'), "
                    "('Legacy Two', 'LEGACY-2', 'Legacy Client', 'fashion', 'ZGZ')"
                )
            )
        command.upgrade(config, "head")
        assert {"skus", "stock_entries", "stock_exits", "incidents", "suppliers"}.issubset(
            inspect(engine).get_table_names()
        )
        assert {"clients", "stockout_events", "inventory_discrepancies"}.issubset(inspect(engine).get_table_names())
        assert set(inspect(engine).get_table_names(schema="reporting")) == {
            "incomplete_weeks",
            "pipeline_runs",
            "source_ledger_state",
            "weekly_warehouse_client_performance",
        }
        pipeline_indexes = {
            index["name"] for index in inspect(engine).get_indexes("pipeline_runs", schema="reporting")
        }
        assert {
            "uq_pipeline_runs_scheduled_date",
            "uq_pipeline_runs_single_active",
            "uq_pipeline_runs_pending_manual",
            "ix_pipeline_runs_claim",
            "ix_pipeline_runs_latest",
        }.issubset(pipeline_indexes)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM reporting.source_ledger_state")) == 1
        sku_columns = {column["name"] for column in inspect(engine).get_columns("skus")}
        assert "client_id" in sku_columns
        assert "client_name" not in sku_columns
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT skus.client_id, clients.display_name FROM skus "
                    "JOIN clients ON clients.id = skus.client_id ORDER BY skus.sku"
                )
            ).all()
        assert len(rows) == 2
        assert rows[0][0] == rows[1][0]
        assert {row[1] for row in rows} == {"Legacy Client"}
        incident_indexes = {index["name"] for index in inspect(engine).get_indexes("incidents")}
        assert "ix_incidents_created_at_id" in incident_indexes

        command.downgrade(config, "20260714_0007")
        assert inspect(engine).get_table_names(schema="reporting") == []
        assert "clients" in inspect(engine).get_table_names()

        command.upgrade(config, "head")
        assert "pipeline_runs" in inspect(engine).get_table_names(schema="reporting")

        command.downgrade(config, "20260713_0005")
        sku_columns = {column["name"] for column in inspect(engine).get_columns("skus")}
        assert "client_name" in sku_columns
        assert "client_id" not in sku_columns
        with engine.connect() as connection:
            legacy_names = connection.execute(text("SELECT DISTINCT client_name FROM skus")).scalars().all()
        assert legacy_names == ["Legacy Client"]

        command.upgrade(config, "head")
        sku_columns = {column["name"] for column in inspect(engine).get_columns("skus")}
        assert {"client_id", "min_stock_threshold"}.issubset(sku_columns)
        assert "client_name" not in sku_columns
        engine.dispose()

        command.downgrade(config, "base")
        engine = create_engine(migration_url)
        assert not {"skus", "stock_entries", "stock_exits", "incidents", "suppliers"}.intersection(
            inspect(engine).get_table_names()
        )
        engine.dispose()
    finally:
        get_settings.cache_clear()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{migration_database}" WITH (FORCE)'))
        admin_engine.dispose()
