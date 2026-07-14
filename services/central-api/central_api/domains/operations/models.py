"""Runtime control state for the live operations feed.

A single-row table acting as a no-redeploy kill switch. The feed reads ``enabled``
each tick; the database-size guard (or an operator) flips it to pause writes without
restarting the worker. The advisory lock guarantees a single writer; this row decides
whether that writer should be writing right now.
"""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import CheckConstraint, Column, DateTime, String
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel

# The control table is always exactly one row, addressed by this fixed id.
CONTROL_ROW_ID = 1


def utc_now() -> datetime:
    return datetime.now(UTC)


class OperationsFeedControl(SQLModel, table=True):
    """Single-row runtime switch for the live operations feed."""

    __tablename__ = "operations_feed_control"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint(f"id = {CONTROL_ROW_ID}", name="ck_operations_feed_control_singleton"),
    )

    id: int = Field(default=CONTROL_ROW_ID, primary_key=True)
    enabled: bool = Field(default=True, nullable=False)
    note: str | None = Field(default=None, sa_column=Column(String(200), nullable=True))
    updated_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
