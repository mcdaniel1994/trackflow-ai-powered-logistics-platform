"""Durable terminal evidence for asynchronous tasks sent to the dead-letter queue."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class AsyncTaskFailure(SQLModel, table=True):
    """One idempotent terminal failure record per Celery task."""

    __tablename__ = "async_task_failures"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("attempt > 0", name="ck_async_task_failures_attempt_positive"),
        UniqueConstraint("task_id", name="uq_async_task_failures_task_id"),
        Index("ix_async_task_failures_failed_at", "failed_at"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), sa_column=Column(String(36), primary_key=True))
    task_id: str = Field(sa_column=Column(String(36), nullable=False))
    operation: str = Field(sa_column=Column(String(64), nullable=False))
    entity_id: str | None = Field(default=None, sa_column=Column(String(36), nullable=True))
    attempt: int = Field(sa_column=Column(Integer, nullable=False))
    error_code: str = Field(sa_column=Column(String(64), nullable=False))
    error_message: str = Field(sa_column=Column(String(200), nullable=False))
    failed_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    dead_lettered_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
