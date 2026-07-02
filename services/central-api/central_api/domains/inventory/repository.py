"""Bounded, aggregate inventory queries and movement writes."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast

from sqlalchemy import (
    String,
    Table,
    func,
    literal,
    null,
    union_all,
)
from sqlalchemy import (
    select as sa_select,
)
from sqlalchemy.engine import Row
from sqlmodel import Session, select

from .models import SKU, StockEntry, StockExit

# SQLModel supplies SQLAlchemy tables dynamically; the casts expose their typed columns.
sku_table = cast(Table, SKU.__table__)  # type: ignore[attr-defined]
entry_table = cast(Table, StockEntry.__table__)  # type: ignore[attr-defined]
exit_table = cast(Table, StockExit.__table__)  # type: ignore[attr-defined]


@dataclass(frozen=True)
class MovementRecord:
    """Repository projection used to build one timeline response without N+1 reads."""

    id: int
    movement_type: str
    sku_id: int
    quantity: int
    reference: str | None
    exit_type: str | None
    tracking_number: str | None
    warehouse: str
    created_at: datetime
    user_uuid: str
    sku: SKU


class InventoryRepository:
    """Keep SQL construction out of routes and business-rule orchestration."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _stock_parts() -> tuple[Any, Any, Any]:
        """Build reusable aggregate subqueries for entry-minus-exit stock."""
        entries = (
            sa_select(
                entry_table.c.sku_id.label("sku_id"),
                entry_table.c.warehouse.label("warehouse"),
                func.sum(entry_table.c.quantity).label("received"),
            )
            .group_by(entry_table.c.sku_id, entry_table.c.warehouse)
            .subquery()
        )
        exits = (
            sa_select(
                exit_table.c.sku_id.label("sku_id"),
                exit_table.c.warehouse.label("warehouse"),
                func.sum(exit_table.c.quantity).label("dispatched"),
            )
            .group_by(exit_table.c.sku_id, exit_table.c.warehouse)
            .subquery()
        )
        current_stock = (func.coalesce(entries.c.received, 0) - func.coalesce(exits.c.dispatched, 0)).label(
            "current_stock"
        )
        return entries, exits, current_stock

    def list_products(self, *, limit: int, offset: int) -> tuple[list[tuple[SKU, int]], int]:
        """Load each SKU and its location-specific stock in one aggregate query."""
        entries, exits, current_stock = self._stock_parts()
        statement = (
            sa_select(SKU, current_stock)
            .outerjoin(
                entries,
                (entries.c.sku_id == sku_table.c.id) & (entries.c.warehouse == sku_table.c.warehouse),
            )
            .outerjoin(
                exits,
                (exits.c.sku_id == sku_table.c.id) & (exits.c.warehouse == sku_table.c.warehouse),
            )
            .order_by(sku_table.c.id)
            .limit(limit)
            .offset(offset)
        )
        rows = self.session.execute(statement).all()
        total = int(self.session.scalar(sa_select(func.count()).select_from(SKU)) or 0)
        return [(cast(SKU, row[0]), int(row[1])) for row in rows], total

    def get_product(self, sku_id: int) -> tuple[SKU, int] | None:
        """Load one SKU and its computed warehouse balance."""
        entries, exits, current_stock = self._stock_parts()
        statement = (
            sa_select(SKU, current_stock)
            .outerjoin(
                entries,
                (entries.c.sku_id == sku_table.c.id) & (entries.c.warehouse == sku_table.c.warehouse),
            )
            .outerjoin(
                exits,
                (exits.c.sku_id == sku_table.c.id) & (exits.c.warehouse == sku_table.c.warehouse),
            )
            .where(sku_table.c.id == sku_id)
        )
        row = self.session.execute(statement).one_or_none()
        if row is None:
            return None
        return cast(SKU, row[0]), int(row[1])

    def get_sku_for_update(self, sku_id: int) -> SKU | None:
        """Serialize movement writes for one SKU/location until transaction end."""
        return self.session.exec(select(SKU).where(sku_table.c.id == sku_id).with_for_update()).one_or_none()

    def current_stock(self, sku_id: int, warehouse: str) -> int:
        """Compute a balance inside the same transaction that holds the SKU lock."""
        received = (
            sa_select(func.coalesce(func.sum(entry_table.c.quantity), 0))
            .where(entry_table.c.sku_id == sku_id, entry_table.c.warehouse == warehouse)
            .scalar_subquery()
        )
        dispatched = (
            sa_select(func.coalesce(func.sum(exit_table.c.quantity), 0))
            .where(exit_table.c.sku_id == sku_id, exit_table.c.warehouse == warehouse)
            .scalar_subquery()
        )
        return int(self.session.scalar(sa_select(received - dispatched)) or 0)

    def add_sku(self, sku: SKU) -> None:
        """Queue a new SKU inside the caller-owned transaction."""
        self.session.add(sku)

    def add_entry(self, entry: StockEntry) -> None:
        """Queue an inbound movement inside the caller-owned transaction."""
        self.session.add(entry)

    def add_exit(self, stock_exit: StockExit) -> None:
        """Queue an outbound movement inside the caller-owned transaction."""
        self.session.add(stock_exit)

    def list_movements(self, *, limit: int, offset: int) -> tuple[list[MovementRecord], int]:
        """Union both movement tables and join SKU data once for the timeline."""
        inbound = sa_select(
            entry_table.c.id.label("id"),
            literal("inbound").label("movement_type"),
            entry_table.c.sku_id.label("sku_id"),
            entry_table.c.quantity.label("quantity"),
            entry_table.c.reference.label("reference"),
            null().cast(String).label("exit_type"),
            null().cast(String).label("tracking_number"),
            entry_table.c.warehouse.label("warehouse"),
            entry_table.c.created_at.label("created_at"),
            entry_table.c.user_uuid.label("user_uuid"),
        )
        outbound = sa_select(
            exit_table.c.id.label("id"),
            literal("outbound").label("movement_type"),
            exit_table.c.sku_id.label("sku_id"),
            exit_table.c.quantity.label("quantity"),
            null().cast(String).label("reference"),
            exit_table.c.exit_type.label("exit_type"),
            exit_table.c.tracking_number.label("tracking_number"),
            exit_table.c.warehouse.label("warehouse"),
            exit_table.c.created_at.label("created_at"),
            exit_table.c.user_uuid.label("user_uuid"),
        )
        movements = union_all(inbound, outbound).subquery()
        statement = (
            sa_select(movements, SKU)
            .join(
                SKU,
                (sku_table.c.id == movements.c.sku_id) & (sku_table.c.warehouse == movements.c.warehouse),
            )
            .order_by(movements.c.created_at.desc(), movements.c.movement_type, movements.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        rows = self.session.execute(statement).all()
        total = int(
            self.session.scalar(
                sa_select(
                    sa_select(func.count()).select_from(entry_table).scalar_subquery()
                    + sa_select(func.count()).select_from(exit_table).scalar_subquery()
                )
            )
            or 0
        )
        return [self._movement_record(row) for row in rows], total

    @staticmethod
    def _movement_record(row: Row[Any]) -> MovementRecord:
        """Translate a SQL projection into a typed service-layer record."""
        mapping = row._mapping
        return MovementRecord(
            id=int(mapping["id"]),
            movement_type=str(mapping["movement_type"]),
            sku_id=int(mapping["sku_id"]),
            quantity=int(mapping["quantity"]),
            reference=cast(str | None, mapping["reference"]),
            exit_type=cast(str | None, mapping["exit_type"]),
            tracking_number=cast(str | None, mapping["tracking_number"]),
            warehouse=str(mapping["warehouse"]),
            created_at=cast(datetime, mapping["created_at"]),
            user_uuid=str(mapping["user_uuid"]),
            sku=cast(SKU, row[-1]),
        )
