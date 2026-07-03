"""SQLModel engine and request-scoped session helpers."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from ..core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create one pooled engine while keeping sessions scoped to individual requests."""
    settings = get_settings()
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_size=5,
        max_overflow=2,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "options": (
                f"-c statement_timeout={settings.database_statement_timeout_ms} "
                f"-c lock_timeout={settings.database_lock_timeout_ms}"
            ),
        },
    )


def get_session() -> Generator[Session, None, None]:
    """Yield a fresh unit of work and always release its connection afterward."""
    with Session(get_engine()) as session:
        yield session
