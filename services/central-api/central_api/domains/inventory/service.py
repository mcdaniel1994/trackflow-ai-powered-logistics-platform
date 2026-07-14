"""Transactional inventory rules and safe persistence-failure translation."""

import logging
from dataclasses import dataclass
from typing import Literal, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session

from .models import SKU, Client, InventoryDiscrepancy, StockEntry, StockExit, StockoutEvent, utc_now
from .repository import InventoryRepository, MovementRecord
from .schemas import (
    Category,
    ClientCreate,
    ClientRead,
    ClientUpdate,
    ExitType,
    InventoryDiscrepancyCreate,
    InventoryDiscrepancyRead,
    MovementPage,
    MovementRead,
    ProductPage,
    SKUCreate,
    SKURead,
    SKUSummary,
    SKUUpdate,
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
    def _product_response(sku: SKU, client_name: str, current_stock: int) -> SKURead:
        if sku.id is None:
            raise RuntimeError("Persisted SKU is missing its primary key")
        return SKURead(
            id=sku.id,
            name=sku.name,
            sku=sku.sku,
            client_id=sku.client_id,
            client_name=client_name,
            category=Category(sku.category),
            warehouse=Warehouse(sku.warehouse),
            min_stock_threshold=sku.min_stock_threshold,
            current_stock=current_stock,
        )

    @staticmethod
    def _client_response(client: Client) -> ClientRead:
        return ClientRead(client_id=client.id, client_name=client.display_name)

    @staticmethod
    def _require_admin(role: str) -> None:
        if role != "admin":
            raise InventoryError(status_code=403, detail="Administrator role required")

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
            items=[self._product_response(sku, client_name, stock) for sku, client_name, stock in rows],
            total=total,
            limit=limit,
            offset=offset,
        )

    def create_sku(self, payload: SKUCreate) -> SKURead:
        """Create a zero-stock SKU while mapping its composite duplicate cleanly."""
        if self.repository.get_client(payload.client_id) is None:
            raise InventoryError(status_code=422, detail="Client not found")
        sku = SKU(**payload.model_dump())
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
            if self._constraint_name(exc) == "skus_client_id_fkey":
                raise InventoryError(status_code=422, detail="Client not found") from exc
            raise self._persistence_failure("create_sku", exc) from exc
        except SQLAlchemyError as exc:
            raise self._persistence_failure("create_sku", exc) from exc
        client = self.repository.get_client(payload.client_id)
        if client is None:
            raise RuntimeError("Persisted SKU client is missing")
        return self._product_response(sku, client.display_name, 0)

    def get_product(self, sku_id: int) -> SKURead:
        try:
            product = self.repository.get_product(sku_id)
        except SQLAlchemyError as exc:
            raise self._persistence_failure("get_product", exc) from exc
        if product is None:
            raise InventoryError(status_code=404, detail="SKU not found")
        return self._product_response(*product)

    def update_sku(self, sku_id: int, payload: SKUUpdate) -> SKURead:
        """Update only the threshold; UUID ownership stays immutable for historical attribution."""
        try:
            sku = self.repository.get_sku_for_update(sku_id)
            if sku is None:
                raise InventoryError(status_code=404, detail="SKU not found")
            if payload.client_id is not None and payload.client_id != sku.client_id:
                raise InventoryError(status_code=409, detail="CLIENT_ID_IMMUTABLE")
            if payload.min_stock_threshold is not None:
                sku.min_stock_threshold = payload.min_stock_threshold
            self.session.add(sku)
            self.session.commit()
            self.session.refresh(sku)
            client = self.repository.get_client(sku.client_id)
            if client is None:
                raise RuntimeError("Persisted SKU client is missing")
            current_stock = self.repository.current_stock(sku_id, sku.warehouse)
        except InventoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            raise self._persistence_failure("update_sku", exc) from exc
        return self._product_response(sku, client.display_name, current_stock)

    def list_clients(self) -> list[ClientRead]:
        try:
            clients = self.repository.list_clients()
        except SQLAlchemyError as exc:
            raise self._persistence_failure("list_clients", exc) from exc
        return [self._client_response(client) for client in clients]

    def create_client(self, payload: ClientCreate, role: str) -> ClientRead:
        self._require_admin(role)
        client = Client(display_name=payload.display_name)
        try:
            self.repository.add_client(client)
            self.session.commit()
            self.session.refresh(client)
        except IntegrityError as exc:
            self.session.rollback()
            if self._constraint_name(exc) == "uq_clients_display_name":
                raise InventoryError(status_code=409, detail="CLIENT_NAME_EXISTS") from exc
            raise self._persistence_failure("create_client", exc) from exc
        except SQLAlchemyError as exc:
            raise self._persistence_failure("create_client", exc) from exc
        return self._client_response(client)

    def rename_client(self, client_id: UUID, payload: ClientUpdate, role: str) -> ClientRead:
        self._require_admin(role)
        try:
            client = self.repository.get_client(client_id)
            if client is None:
                raise InventoryError(status_code=404, detail="Client not found")
            client.display_name = payload.display_name
            client.updated_at = utc_now()
            self.session.add(client)
            self.session.commit()
            self.session.refresh(client)
        except InventoryError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            if self._constraint_name(exc) == "uq_clients_display_name":
                raise InventoryError(status_code=409, detail="CLIENT_NAME_EXISTS") from exc
            raise self._persistence_failure("rename_client", exc) from exc
        except SQLAlchemyError as exc:
            raise self._persistence_failure("rename_client", exc) from exc
        return self._client_response(client)

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
            self.session.flush()
            after = available - payload.quantity
            # The locked before/after values and event share one commit, so the
            # threshold history can never disagree with its triggering movement.
            if sku.min_stock_threshold > 0 and available > sku.min_stock_threshold >= after:
                if stock_exit.id is None:
                    raise RuntimeError("Persisted stock exit is missing its primary key")
                self.repository.add_stockout_event(
                    StockoutEvent(
                        sku_id=payload.sku_id,
                        warehouse=payload.warehouse.value,
                        client_id=sku.client_id,
                        threshold_at_event=sku.min_stock_threshold,
                        stock_after=after,
                        stock_exit_id=stock_exit.id,
                        occurred_at=stock_exit.created_at,
                    )
                )
            self.session.commit()
            self.session.refresh(stock_exit)
        except InventoryError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            raise self._persistence_failure("record_outbound", exc) from exc
        return StockExitRead.model_validate(stock_exit)

    def record_discrepancy(
        self,
        payload: InventoryDiscrepancyCreate,
        user_uuid: str | None,
        *,
        source: Literal["manual", "feed"] = "manual",
    ) -> InventoryDiscrepancyRead:
        """Validate and store one discrepancy occurrence for a dispatch order."""
        try:
            stock_exit = self.repository.get_exit(payload.stock_exit_id)
            if stock_exit is None:
                raise InventoryError(status_code=404, detail="Stock exit not found")
            if stock_exit.exit_type != ExitType.DISPATCH.value:
                raise InventoryError(status_code=422, detail="Discrepancy requires a dispatch stock exit")
            if self.repository.discrepancy_exists(payload.stock_exit_id):
                raise InventoryError(status_code=409, detail="DISCREPANCY_EXISTS")
            sku = self.repository.get_sku_for_update(stock_exit.sku_id)
            if sku is None or sku.warehouse != stock_exit.warehouse:
                raise InventoryError(status_code=422, detail="Stock exit SKU ownership is invalid")
            discrepancy = InventoryDiscrepancy(
                stock_exit_id=payload.stock_exit_id,
                sku_id=stock_exit.sku_id,
                warehouse=stock_exit.warehouse,
                client_id=sku.client_id,
                quantity_delta=payload.quantity_delta,
                source=source,
                created_by_user_uuid=user_uuid,
            )
            self.repository.add_discrepancy(discrepancy)
            self.session.commit()
            self.session.refresh(discrepancy)
        except InventoryError:
            self.session.rollback()
            raise
        except IntegrityError as exc:
            self.session.rollback()
            if self._constraint_name(exc) == "uq_inventory_discrepancies_stock_exit_id":
                raise InventoryError(status_code=409, detail="DISCREPANCY_EXISTS") from exc
            raise self._persistence_failure("record_discrepancy", exc) from exc
        except SQLAlchemyError as exc:
            raise self._persistence_failure("record_discrepancy", exc) from exc
        return InventoryDiscrepancyRead.model_validate(discrepancy)

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
            sku=SKUSummary(
                id=record.sku.id,
                name=record.sku.name,
                sku=record.sku.sku,
                client_id=record.sku.client_id,
                client_name=record.client_name,
                category=Category(record.sku.category),
                warehouse=Warehouse(record.sku.warehouse),
                min_stock_threshold=record.sku.min_stock_threshold,
            ),
        )
