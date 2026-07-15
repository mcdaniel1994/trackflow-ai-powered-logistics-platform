"""Approval-gated production migration with role, lock, grant, and head checks."""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Connection, Engine, create_engine, text

from central_api.core.config import get_settings

SERVICE_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_LOCK_KEY = 4_306_160_006_001
ALLOWED_SCHEMAS = ("public", "reporting")
EXPECTED_MIGRATION_ROLE = "trackflow_migration"
RUNTIME_ROLE = "trackflow_runtime"
_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


class MigrationSafetyError(RuntimeError):
    """Base class for fixed, non-sensitive production migration failures."""


class MigrationConfigurationError(MigrationSafetyError):
    pass


class MigrationRoleError(MigrationSafetyError):
    pass


class MigrationLockError(MigrationSafetyError):
    pass


class MigrationVerificationError(MigrationSafetyError):
    pass


@dataclass(frozen=True)
class MigrationResult:
    before_revision: str
    after_revision: str
    runtime_grants_verified: bool


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MigrationConfigurationError(f"{name} is required")
    return value


def _role_name(name: str, default: str) -> str:
    value = os.environ.get(name, default).strip()
    if not _IDENTIFIER.fullmatch(value):
        raise MigrationConfigurationError(f"{name} is invalid")
    return value


def _revision(connection: Connection) -> str:
    exists = connection.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL"))
    if not exists:
        return "base"
    return str(connection.scalar(text("SELECT version_num FROM public.alembic_version")) or "base")


def _verify_migration_role(connection: Connection, expected_role: str, runtime_role: str) -> None:
    current_user = str(connection.scalar(text("SELECT current_user")))
    if current_user != expected_role or current_user == runtime_role:
        raise MigrationRoleError("unexpected migration identity")
    role = connection.execute(
        text(
            "SELECT rolsuper, rolcreatedb, rolcreaterole FROM pg_roles "
            "WHERE rolname = current_user"
        )
    ).one()
    if any(bool(value) for value in role):
        raise MigrationRoleError("migration identity has forbidden role attributes")
    can_create_schema = connection.scalar(
        text("SELECT has_database_privilege(current_user, current_database(), 'CREATE')")
    )
    if not can_create_schema:
        raise MigrationRoleError("migration identity lacks database CREATE")


def _apply_runtime_grants(connection: Connection, runtime_role: str) -> None:
    for schema in ALLOWED_SCHEMAS:
        connection.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{runtime_role}"'))
        connection.execute(
            text(
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" '
                f'TO "{runtime_role}"'
            )
        )
        connection.execute(
            text(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{schema}" TO "{runtime_role}"')
        )
        connection.execute(
            text(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                f'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{runtime_role}"'
            )
        )
        connection.execute(
            text(
                f'ALTER DEFAULT PRIVILEGES IN SCHEMA "{schema}" '
                f'GRANT USAGE ON SEQUENCES TO "{runtime_role}"'
            )
        )


def _verify_runtime_grants(connection: Connection, runtime_role: str) -> None:
    for schema in ALLOWED_SCHEMAS:
        if not connection.scalar(
            text("SELECT has_schema_privilege(:runtime_role, :schema, 'USAGE')"),
            {"runtime_role": runtime_role, "schema": schema},
        ):
            raise MigrationVerificationError("runtime schema grant verification failed")

    objects = connection.execute(
        text(
            "SELECT n.nspname, c.relname, c.relkind FROM pg_class AS c "
            "JOIN pg_namespace AS n ON n.oid = c.relnamespace "
            "WHERE n.nspname IN ('public', 'reporting') AND c.relkind IN ('r', 'p', 'S')"
        )
    ).all()
    for schema, object_name, object_type in objects:
        qualified = f'"{schema}"."{object_name}"'
        if object_type == "S":
            granted = connection.scalar(
                text("SELECT has_sequence_privilege(:role, :object, 'USAGE')"),
                {"role": runtime_role, "object": qualified},
            )
        else:
            granted = connection.scalar(
                text("SELECT has_table_privilege(:role, :object, 'SELECT,INSERT,UPDATE,DELETE')"),
                {"role": runtime_role, "object": qualified},
            )
        if not granted:
            raise MigrationVerificationError("runtime object grant verification failed")

    defaults = {
        (str(schema), str(object_type), str(privilege))
        for schema, object_type, privilege in connection.execute(
            text(
                "SELECT n.nspname, defaults.defaclobjtype, acl.privilege_type "
                "FROM pg_default_acl AS defaults "
                "JOIN pg_namespace AS n ON n.oid = defaults.defaclnamespace "
                "CROSS JOIN LATERAL aclexplode(defaults.defaclacl) AS acl "
                "JOIN pg_roles AS grantee ON grantee.oid = acl.grantee "
                "WHERE defaults.defaclrole = (SELECT oid FROM pg_roles WHERE rolname = current_user) "
                "AND grantee.rolname = :runtime_role AND n.nspname IN ('public', 'reporting')"
            ),
            {"runtime_role": runtime_role},
        )
    }
    for schema in ALLOWED_SCHEMAS:
        table_privileges = {"SELECT", "INSERT", "UPDATE", "DELETE"}
        if not table_privileges.issubset(
            {
                privilege
                for found_schema, object_type, privilege in defaults
                if found_schema == schema and object_type == "r"
            }
        ):
            raise MigrationVerificationError("runtime default table grants verification failed")
        if (schema, "S", "USAGE") not in defaults:
            raise MigrationVerificationError("runtime default sequence grants verification failed")


def _alembic_config() -> Config:
    return Config(str(SERVICE_ROOT / "alembic.ini"))


def migrate() -> MigrationResult:
    migration_url = _required_environment("MIGRATION_DATABASE_URL")
    expected_role = _role_name("MIGRATION_ROLE", EXPECTED_MIGRATION_ROLE)
    runtime_role = _role_name("RUNTIME_ROLE", RUNTIME_ROLE)
    if expected_role == runtime_role:
        raise MigrationConfigurationError("migration and runtime roles must differ")

    engine: Engine = create_engine(migration_url, pool_pre_ping=True)
    lock_connection = engine.connect()
    acquired = False
    try:
        _verify_migration_role(lock_connection, expected_role, runtime_role)
        before = _revision(lock_connection)
        acquired = bool(
            lock_connection.scalar(
                text("SELECT pg_try_advisory_lock(:lock_key)"),
                {"lock_key": MIGRATION_LOCK_KEY},
            )
        )
        if not acquired:
            raise MigrationLockError("migration advisory lock is already held")

        # Alembic reads only MIGRATION_DATABASE_URL in production. Clear the
        # process cache so programmatic invocations cannot reuse stale settings.
        get_settings.cache_clear()
        config = _alembic_config()
        command.upgrade(config, "head")

        with engine.begin() as connection:
            _apply_runtime_grants(connection, runtime_role)
            _verify_runtime_grants(connection, runtime_role)
            after = _revision(connection)
            expected_head = ScriptDirectory.from_config(config).get_current_head()
            if after != expected_head:
                raise MigrationVerificationError("database revision does not match image head")
        return MigrationResult(before, after, True)
    finally:
        if acquired:
            lock_connection.execute(
                text("SELECT pg_advisory_unlock(:lock_key)"),
                {"lock_key": MIGRATION_LOCK_KEY},
            )
        lock_connection.close()
        engine.dispose()


def entrypoint() -> None:
    try:
        result = migrate()
    except Exception as exc:
        print(f"production_migration_failed error_type={type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
    print(
        "production_migration_complete "
        f"before_revision={result.before_revision} after_revision={result.after_revision} "
        "runtime_grants=verified"
    )


if __name__ == "__main__":
    entrypoint()
