"""Production migration role, lock, grant, retry, and fail-closed proofs."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from central_api.core.config import Settings, get_settings
from scripts import production_migrate

SERVICE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def role_database(database_url: str, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    database_name = "trackflow_production_migrate_test"
    parsed = make_url(database_url)
    admin_engine = create_engine(parsed.set(database="postgres"), isolation_level="AUTOCOMMIT")
    admin_database_url = parsed.set(database=database_name)
    migration_url = admin_database_url.set(username="trackflow_migration", password="migration_test_local")
    runtime_url = admin_database_url.set(username="trackflow_runtime", password="runtime_test_local")

    with admin_engine.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
        connection.execute(text("DROP ROLE IF EXISTS trackflow_runtime"))
        connection.execute(text("DROP ROLE IF EXISTS trackflow_migration"))
        connection.execute(text("CREATE ROLE trackflow_runtime LOGIN PASSWORD 'runtime_test_local'"))
        connection.execute(text("CREATE ROLE trackflow_migration LOGIN PASSWORD 'migration_test_local'"))
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        connection.execute(text(f'GRANT CONNECT, CREATE ON DATABASE "{database_name}" TO trackflow_migration'))
        connection.execute(text(f'GRANT CONNECT ON DATABASE "{database_name}" TO trackflow_runtime'))

    database_admin = create_engine(admin_database_url)
    with database_admin.begin() as connection:
        connection.execute(text("GRANT USAGE, CREATE ON SCHEMA public TO trackflow_migration"))

    rendered_migration_url = migration_url.render_as_string(hide_password=False)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", rendered_migration_url)
    monkeypatch.setenv("MIGRATION_DATABASE_URL", rendered_migration_url)
    get_settings.cache_clear()
    command.upgrade(Config(str(SERVICE_ROOT / "alembic.ini")), "20260714_0008")

    try:
        yield migration_url, runtime_url
    finally:
        get_settings.cache_clear()
        database_admin.dispose()
        with admin_engine.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)'))
            connection.execute(text("DROP ROLE IF EXISTS trackflow_runtime"))
            connection.execute(text("DROP ROLE IF EXISTS trackflow_migration"))
        admin_engine.dispose()


def test_production_migration_upgrades_grants_and_reruns_idempotently(role_database) -> None:  # type: ignore[no-untyped-def]
    migration_url, runtime_url = role_database
    first = production_migrate.migrate()
    second = production_migrate.migrate()
    assert first.before_revision == "20260714_0008"
    assert first.after_revision == "20260716_0010"
    assert second.before_revision == second.after_revision == "20260716_0010"

    migration_engine = create_engine(migration_url)
    with migration_engine.begin() as connection:
        connection.execute(text("CREATE TABLE reporting.future_grant_probe (id serial PRIMARY KEY)"))

    runtime_engine = create_engine(runtime_url)
    with runtime_engine.begin() as connection:
        connection.execute(text("INSERT INTO reporting.future_grant_probe DEFAULT VALUES"))
        assert connection.scalar(text("SELECT count(*) FROM reporting.future_grant_probe")) == 1
        assert connection.scalar(text("SELECT count(*) FROM reporting.worker_heartbeats")) == 0
    runtime_engine.dispose()
    migration_engine.dispose()


def test_production_migration_rejects_wrong_role_and_held_lock(
    role_database,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # type: ignore[no-untyped-def]
    migration_url, runtime_url = role_database
    monkeypatch.setenv("MIGRATION_DATABASE_URL", runtime_url.render_as_string(hide_password=False))
    with pytest.raises(production_migrate.MigrationRoleError):
        production_migrate.migrate()

    monkeypatch.setenv("MIGRATION_DATABASE_URL", migration_url.render_as_string(hide_password=False))
    lock_engine = create_engine(migration_url)
    with lock_engine.connect() as connection:
        assert connection.scalar(
            text("SELECT pg_try_advisory_lock(:key)"),
            {"key": production_migrate.MIGRATION_LOCK_KEY},
        )
        with pytest.raises(production_migrate.MigrationLockError):
            production_migrate.migrate()
    lock_engine.dispose()


def test_production_alembic_url_fails_closed_without_migration_secret() -> None:
    settings = Settings(database_url="postgresql://runtime:secret@localhost/database", app_env="production")
    with pytest.raises(ValueError, match="MIGRATION_DATABASE_URL"):
        _ = settings.alembic_database_url


def test_entrypoint_never_logs_exception_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        production_migrate,
        "migrate",
        lambda: (_ for _ in ()).throw(RuntimeError("postgresql://user:secret@private/database")),
    )
    with pytest.raises(SystemExit):
        production_migrate.entrypoint()
    error = capsys.readouterr().err
    assert "RuntimeError" in error
    assert "secret" not in error
    assert "private" not in error
