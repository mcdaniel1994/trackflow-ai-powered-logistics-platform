"""Alembic environment for the Central API's versioned PostgreSQL schema."""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from central_api.core.config import get_settings
from central_api.domains.inventory import models as inventory_models  # noqa: F401
from central_api.domains.suppliers import models as supplier_models  # noqa: F401

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Importing the domain models registers tables on SQLModel metadata for autogeneration.
target_metadata = SQLModel.metadata


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
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations through a short-lived non-pooled migration connection."""
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = database_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
