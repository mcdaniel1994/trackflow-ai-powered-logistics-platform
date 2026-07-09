"""Transactional inventory rules and safe persistence-failure translation."""

import logging
from dataclasses import dataclass
from typing import Literal, cast

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session

from .models import SKU, StockEntry, StockExit
from .repository import InventoryRepository, MovementRecord
from .schemas import (
    Category,
    ExitType,
    MovementPage,
    MovementRead,
    ProductPage,
    SKUCreate,
    SKURead,
    SKUSummary,
    StockEntryCreate,
    StockEntryRead,
    StockExitCreate,
    StockExitRead,
    Warehouse,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DispatchRejection:
    """Safe, PII-free metadata for a rejected dispatch, used for best-effort telemetry."""

    warehouse: str
    reason_code: str
    quantity: int | None


@dataclass
class InventoryError(Exception):
    """Typed domain failure translated to HTTP only at the application boundary."""

    status_code: int
    detail: str
    # Populated only for rejected DISPATCH attempts so the boundary can emit a
    # best-effort `inventory.dispatch.rejected` telemetry event after the response.
    reject_event: DispatchRejection | None = None


class InventoryService:
    """Coordinate database locks, inventory rules, and atomic commits."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = InventoryRepository(session)

    @staticmethod
    def _product_response(sku: SKU, current_stock: int) -> SKURead:
        if sku.id is None:
            raise RuntimeError("Persisted SKU is missing its primary key")
        return SKURead(
            id=sku.id,
            name=sku.name,
            sku=sku.sku,
            client_name=sku.client_name,
            category=Category(sku.category),
            warehouse=Warehouse(sku.warehouse),
            current_stock=current_stock,
        )

    @staticmethod
    def _constraint_name(exc: IntegrityError) -> str | None:
        """Read only the driver constraint identifier, never SQL parameters."""
        return getattr(getattr(exc.orig, "diag", None), "constraint_name", None)

    def _persistence_failure(self, operation: str, exc: SQLAlchemyError) -> InventoryError:
        """Log safe diagnostics without connection URLs, statements, or payload values."""
        self.session.rollback()
        logger.error(
            "inventory_database_failure operation=%s error_type=%s",
            operation,
            type(exc).__name__,
        )
        return InventoryError(status_code=503, detail="Inventory service temporarily unavailable")

    def list_products(self, *, limit: int, offset: int) -> ProductPage:
        try:
            rows, total = self.repository.list_products(limit=limit, offset=offset)
        except SQLAlchemyError as exc:
            raise self._persistence_failure("list_products", exc) from exc
        return ProductPage(
            items=[self._product_response(sku, stock) for sku, stock in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def create_sku(self, payload: SKUCreate) -> SKURead:
        """Create a zero-stock SKU while mapping its composite duplicate cleanly."""
        sku = SKU(**payload.model_dump(mode="json"))
        try:
            self.repository.add_sku(sku)
            self.session.commit()
            self.session.refresh(sku)
        except IntegrityError as exc:
            self.session.rollback()
            if self._constraint_name(exc) == "uq_skus_sku_warehouse":
                raise InventoryError(
                    status_code=409,
                    detail=f"SKU '{payload.sku}' already exists in warehouse '{payload.warehouse.value}'",
                ) from exc
            raise self._persistence_failure("create_sku", exc) from exc
        except SQLAlchemyError as exc:
            raise self._persistence_failure("create_sku", exc) from exc
        return self._product_response(sku, 0)

    def get_product(self, sku_id: int) -> SKURead:
        try:
            product = self.repository.get_product(sku_id)
        except SQLAlchemyError as exc:
            raise self._persistence_failure("get_product", exc) from exc
        if product is None:
            raise InventoryError(status_code=404, detail="SKU not found")
        return self._product_response(*product)

    def record_inbound(self, payload: StockEntryCreate, user_uuid: str) -> StockEntryRead:
        """Lock the SKU and commit the receipt as one indivisible unit."""
        try:
            sku = self.repository.get_sku_for_update(payload.sku_id)
            self._validate_sku_warehouse(sku, payload.warehouse.value)
            entry = StockEntry(
                sku_id=payload.sku_id,
                quantity=payload.quantity,
                reference=payload.reference,
                warehouse=payload.warehouse.value,
                user_uuid=user_uuid,
            )
            self.repository.add_entry(entry)
            self.session.commit()
            self.session.refresh(entry)
        except InventoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            raise self._persistence_failure("record_inbound", exc) from exc
        return StockEntryRead.model_validate(entry)

    @staticmethod
    def _dispatch_rejection(payload: StockExitCreate, reason_code: str) -> DispatchRejection | None:
        """Describe a rejected DISPATCH for best-effort telemetry; None for a loss."""
        if payload.exit_type != ExitType.DISPATCH:
            return None
        return DispatchRejection(
            warehouse=payload.warehouse.value,
            reason_code=reason_code,
            quantity=payload.quantity,
        )

    def record_outbound(self, payload: StockExitCreate, user_uuid: str) -> StockExitRead:
        """Serialize stock calculation and exit creation to prevent negative races."""
        try:
            sku = self.repository.get_sku_for_update(payload.sku_id)
            if sku is None:
                raise InventoryError(
                    status_code=404,
                    detail="SKU not found",
                    reject_event=self._dispatch_rejection(payload, "SKU_NOT_FOUND"),
                )
            if sku.warehouse != payload.warehouse.value:
                raise InventoryError(
                    status_code=400,
                    detail="Movement warehouse must match SKU warehouse",
                    reject_event=self._dispatch_rejection(payload, "WAREHOUSE_MISMATCH"),
                )
            available = self.repository.current_stock(payload.sku_id, payload.warehouse.value)
            if payload.quantity > available:
                raise InventoryError(
                    status_code=400,
                    detail=(
                        f"Insufficient stock for SKU '{sku.sku}'. Available: {available}, "
                        f"requested: {payload.quantity}."
                    ),
                    reject_event=self._dispatch_rejection(payload, "INSUFFICIENT_STOCK"),
                )
            stock_exit = StockExit(
                sku_id=payload.sku_id,
                quantity=payload.quantity,
                exit_type=payload.exit_type.value,
                tracking_number=payload.tracking_number,
                warehouse=payload.warehouse.value,
                user_uuid=user_uuid,
            )
            self.repository.add_exit(stock_exit)
            self.session.commit()
            self.session.refresh(stock_exit)
        except InventoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            raise self._persistence_failure("record_outbound", exc) from exc
        return StockExitRead.model_validate(stock_exit)

    def list_movements(self, *, limit: int, offset: int) -> MovementPage:
        try:
            records, total = self.repository.list_movements(limit=limit, offset=offset)
        except SQLAlchemyError as exc:
            raise self._persistence_failure("list_movements", exc) from exc
        return MovementPage(
            items=[self._movement_response(record) for record in records],
            total=total,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _validate_sku_warehouse(sku: SKU | None, warehouse: str) -> None:
        """Differentiate an unknown SKU from a cross-warehouse movement attempt."""
        if sku is None:
            raise InventoryError(status_code=404, detail="SKU not found")
        if sku.warehouse != warehouse:
            raise InventoryError(status_code=400, detail="Movement warehouse must match SKU warehouse")

    @staticmethod
    def _movement_response(record: MovementRecord) -> MovementRead:
        """Build the documented flat timeline shape with nested SKU metadata."""
        movement_type = cast(Literal["inbound", "outbound"], record.movement_type)
        return MovementRead(
            id=record.id,
            movement_type=movement_type,
            sku_id=record.sku_id,
            quantity=record.quantity,
            reference=record.reference,
            exit_type=ExitType(record.exit_type) if record.exit_type is not None else None,
            tracking_number=record.tracking_number,
            warehouse=Warehouse(record.warehouse),
            created_at=record.created_at,
            user_uuid=record.user_uuid,
            sku=SKUSummary.model_validate(record.sku),
        )
