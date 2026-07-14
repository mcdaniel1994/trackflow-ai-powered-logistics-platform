"""SQLModel persistence tables for location-specific inventory movements."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    """Generate timezone-aware UTC timestamps for authoritative movement records."""
    return datetime.now(UTC)


class Client(SQLModel, table=True):
    """Stable client identity; display names may change without moving history."""

    __tablename__ = "clients"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        UniqueConstraint("display_name", name="uq_clients_display_name"),
    )

    id: UUID = Field(
        default_factory=uuid4,
        sa_column=Column(PGUUID(as_uuid=True), primary_key=True, nullable=False),
    )
    display_name: str = Field(sa_column=Column(String(160), nullable=False))
    created_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    updated_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))


class SKU(SQLModel, table=True):
    """A client SKU at one physical TrackFlow warehouse."""

    __tablename__ = "skus"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        UniqueConstraint("sku", "warehouse", name="uq_skus_sku_warehouse"),
        # PostgreSQL requires the exact referenced column set to be unique.
        UniqueConstraint("id", "warehouse", name="uq_skus_id_warehouse"),
        CheckConstraint("category IN ('fashion', 'electronics', 'cosmetics')", name="ck_skus_category"),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_skus_warehouse"),
        CheckConstraint("min_stock_threshold >= 0", name="ck_skus_min_stock_threshold_nonnegative"),
    )

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(sa_column=Column(String(200), nullable=False))
    sku: str = Field(sa_column=Column(String(80), nullable=False))
    client_id: UUID = Field(
        sa_column=Column(
            PGUUID(as_uuid=True),
            ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )
    )
    min_stock_threshold: int = Field(default=0, nullable=False)
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


class StockoutEvent(SQLModel, table=True):
    """Authoritative record of one downward minimum-stock threshold crossing."""

    __tablename__ = "stockout_events"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_stockout_events_sku_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_stockout_events_warehouse"),
        CheckConstraint("threshold_at_event > 0", name="ck_stockout_events_threshold_positive"),
        UniqueConstraint("stock_exit_id", name="uq_stockout_events_stock_exit_id"),
        Index("ix_stockout_events_warehouse_client_occurred_at", "warehouse", "client_id", "occurred_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    sku_id: int = Field(nullable=False)
    warehouse: str = Field(sa_column=Column(String(3), nullable=False))
    client_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    )
    threshold_at_event: int = Field(nullable=False)
    stock_after: int = Field(nullable=False)
    stock_exit_id: int = Field(
        sa_column=Column(ForeignKey("stock_exits.id", ondelete="RESTRICT"), nullable=False)
    )
    occurred_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))


class InventoryDiscrepancy(SQLModel, table=True):
    """One discrepancy occurrence per dispatch order for exact rate reporting."""

    __tablename__ = "inventory_discrepancies"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        ForeignKeyConstraint(
            ["sku_id", "warehouse"],
            ["skus.id", "skus.warehouse"],
            name="fk_inventory_discrepancies_sku_warehouse",
            ondelete="RESTRICT",
        ),
        CheckConstraint("warehouse IN ('LA', 'ZGZ')", name="ck_inventory_discrepancies_warehouse"),
        CheckConstraint("quantity_delta <> 0", name="ck_inventory_discrepancies_quantity_delta_nonzero"),
        CheckConstraint("source IN ('manual', 'feed')", name="ck_inventory_discrepancies_source"),
        UniqueConstraint("stock_exit_id", name="uq_inventory_discrepancies_stock_exit_id"),
        Index(
            "ix_inventory_discrepancies_warehouse_client_detected_at",
            "warehouse",
            "client_id",
            "detected_at",
        ),
    )

    id: int | None = Field(default=None, primary_key=True)
    stock_exit_id: int = Field(
        sa_column=Column(ForeignKey("stock_exits.id", ondelete="RESTRICT"), nullable=False)
    )
    sku_id: int = Field(nullable=False)
    warehouse: str = Field(sa_column=Column(String(3), nullable=False))
    client_id: UUID = Field(
        sa_column=Column(PGUUID(as_uuid=True), ForeignKey("clients.id", ondelete="RESTRICT"), nullable=False)
    )
    quantity_delta: int = Field(nullable=False)
    source: str = Field(sa_column=Column(String(16), nullable=False))
    detected_at: datetime = Field(default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False))
    created_by_user_uuid: str | None = Field(default=None, sa_column=Column(String(36), nullable=True))
