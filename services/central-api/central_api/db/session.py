"""SQLModel engine and request-scoped session helpers."""

import logging
from collections.abc import Generator
from functools import lru_cache
from threading import Lock

from pipelines.database import ObservedQueuePool
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from ..core.config import Settings, get_settings

logger = logging.getLogger(__name__)
_engine_lock = Lock()


@lru_cache
def _cached_engine() -> Engine:
    return create_runtime_engine(get_settings())


def get_engine() -> Engine:
    """Serialize cold initialization: lru_cache alone can construct concurrent pools."""
    with _engine_lock:
        return _cached_engine()


def dispose_engine() -> None:
    """Close the process pool after requests/background work have finished."""
    with _engine_lock:
        if _cached_engine.cache_info().currsize:
            _cached_engine().dispose()
        _cached_engine.cache_clear()


def create_runtime_engine(settings: Settings) -> Engine:
    """Construct a service pool with its explicit budget and safe diagnostics."""
    logger.info(
        "database_pool_configured service=%s size=%s max_overflow=%s timeout_seconds=%s",
        settings.database_service_name, settings.database_pool_size,
        settings.database_max_overflow, settings.database_pool_timeout_seconds,
    )
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_recycle=300,
        poolclass=ObservedQueuePool,
        pool_logging_name=settings.database_service_name,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout_seconds,
        connect_args={
            "connect_timeout": settings.database_connect_timeout_seconds,
            "application_name": f"trackflow:{settings.database_service_name}",
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
