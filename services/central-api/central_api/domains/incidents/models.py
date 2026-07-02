"""SQLModel persistence for operational incidents."""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import CheckConstraint, Column, DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel
from trackflow_incidents import BRANCH_VALUES, CATEGORY_VALUES, ORIGIN_VALUES, STATUS_VALUES


def utc_now() -> datetime:
    return datetime.now(UTC)


def sql_values(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Incident(SQLModel, table=True):
    """One authoritative operational incident and its lifecycle state."""

    __tablename__ = "incidents"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint(f"category IN ({sql_values(CATEGORY_VALUES)})", name="ck_incidents_category"),
        CheckConstraint(f"status IN ({sql_values(STATUS_VALUES)})", name="ck_incidents_status"),
        CheckConstraint(f"origin IN ({sql_values(ORIGIN_VALUES)})", name="ck_incidents_origin"),
        CheckConstraint(f"branch IN ({sql_values(BRANCH_VALUES)})", name="ck_incidents_branch"),
        UniqueConstraint("import_key_hash", name="uq_incidents_import_key_hash"),
        Index("ix_incidents_status", "status"),
        Index("ix_incidents_category", "category"),
        Index("ix_incidents_origin", "origin"),
        Index("ix_incidents_branch", "branch"),
        Index("ix_incidents_created_at_id", "created_at", "id"),
    )

    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(sa_column=Column(String(200), nullable=False))
    description: str = Field(sa_column=Column(Text, nullable=False))
    category: str = Field(sa_column=Column(String(32), nullable=False))
    status: str = Field(sa_column=Column(String(16), nullable=False))
    origin: str = Field(sa_column=Column(String(16), nullable=False))
    branch: str = Field(sa_column=Column(String(32), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_by_user_uuid: str | None = Field(default=None, sa_column=Column(String(36), nullable=True))
    import_key_hash: str | None = Field(default=None, sa_column=Column(String(64), nullable=True))

