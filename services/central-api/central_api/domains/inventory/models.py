"""SQLModel persistence tables for location-specific inventory movements."""

from datetime import UTC, datetime
from typing import ClassVar

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Generate timezone-aware UTC timestamps for authoritative movement records."""
    return datetime.now(UTC)


class SKU(SQLModel, table=True):
    """A client SKU at one physical TrackFlow warehouse."""

    __tablename__ = "skus"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        UniqueConstraint("sku", "warehouse", name="uq_skus_sku_warehouse"),
        # PostgreSQL requires the exact referenced column set to be unique.
        UniqueConstraint("id", "warehouse", name="uq_skus_id_warehouse"),
        CheckConstraint("category IN ('fashion', 'electronics', 'cosmetics')", name="ck_skus_category"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_skus_warehouse"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(200), nullable=False))
    sku: str = Field(sa_column=Column(String(80), nullable=False))
    client_name: str = Field(sa_column=Column(String(160), nullable=False))
    category: str = Field(sa_column=Column(String(32), nullable=False))
    warehouse: str = Field(sa_column=Column(String(3), nullable=False))


class StockEntry(SQLModel, table=True):
    """An immutable goods receipt recorded against a warehouse SKU."""

    __tablename__ = "stock_entries"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stock_entries_sku_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_entries_quantity_positive"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_entries_warehouse"),
        Index("ix_stock_entries_sku_warehouse_created_at", "sku_id", "warehouse", "created_at"),
        Index("ix_stock_entries_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(nullable=False)
    quantity: int = Field(nullable=False)
    reference: str = Field(sa_column=Column(String(120), nullable=False))
    warehouse: str = Field(sa_column=Column(String(3), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    user_uuid: str = Field(sa_column=Column(String(36), nullable=False))


class StockExit(SQLModel, table=True):
    """An immutable dispatch or confirmed-loss movement."""

    __tablename__ = "stock_exits"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stock_exits_sku_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint("quantity > 0", name="ck_stock_exits_quantity_positive"),
        CheckConstraint("exit_type IN ('dispatch', 'loss')", name="ck_stock_exits_exit_type"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stock_exits_warehouse"),
        CheckConstraint(
            "(exit_type = 'dispatch' AND tracking_number IS NOT NULL) OR "
            "(exit_type = 'loss' AND tracking_number IS NULL)",
            name="ck_stock_exits_tracking_rule",
        ),
        Index("ix_stock_exits_sku_warehouse_created_at", "sku_id", "warehouse", "created_at"),
        Index("ix_stock_exits_created_at", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(nullable=False)
    quantity: int = Field(nullable=False)
    exit_type: str = Field(sa_column=Column(String(16), nullable=False))
    tracking_number: str | None = Field(default=None, sa_column=Column(String(120), nullable=True))
    warehouse: str = Field(sa_column=Column(String(3), nullable=False))
    created_at: datetime = Field(
        default_factory=utc_now,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    user_uuid: str = Field(sa_column=Column(String(36), nullable=False))
