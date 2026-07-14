"""Alembic environment for the Central API's versioned PostgreSQL schema."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from central_api.core.config import get_settings
from central_api.domains.incidents import models as incident_models  # noqa: F401
from central_api.domains.inventory import models as inventory_models  # noqa: F401
from central_api.domains.operations import models as operations_models  # noqa: F401
from central_api.domains.reporting import models as reporting_models  # noqa: F401
from central_api.domains.suppliers import models as supplier_models  # noqa: F401
from central_api.domains.telemetry import models as telemetry_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing the domain models registers tables on SQLModel metadata for autogeneration.
target_metadata = SQLModel.metadata


def include_object(
    _object: object,
    _name: str | None,
    _type: str,
    _reflected: bool,
    _compare_to: object | None,
) -> bool:
    """Keep future autogeneration away from provider-managed schemas."""
    if _type == "table" and _name == "alembic_version":
        return False
    schema = getattr(_object, "schema", None)
    return schema in {None, "public", "reporting"}


def database_url() -> str:
    """Escape interpolation markers before passing the secret URL to Alembic config."""
    return get_settings().alembic_database_url.replace("%", "%%")


def run_migrations_offline() -> None:
    """Render SQL without creating an Engine, useful for migration review."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        include_schemas=True,
        include_object=include_object,
        version_table_schema="public",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations through a short-lived non-pooled migration connection."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            include_schemas=True,
            include_object=include_object,
            version_table_schema="public",
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
