"""Strict request and response contracts for the inventory API."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Warehouse(StrEnum):
    """Physical TrackFlow locations represented in the shared inventory tables."""

    LA = "LA"
    ZGZ = "ZGZ"


class Category(StrEnum):
    """Engagement 5's permitted SKU categories."""

    FASHION = "fashion"
    ELECTRONICS = "electronics"
    COSMETICS = "cosmetics"


class ExitType(StrEnum):
    """Reasons stock may leave a warehouse."""

    DISPATCH = "dispatch"
    LOSS = "loss"


class APIModel(BaseModel):
    """Deny undocumented input and support response conversion from SQLModel rows."""

    model_config = ConfigDict(extra="forbid", from_attributes=True, str_strip_whitespace=True)


class SKUCreate(APIModel):
    """Client-writable fields for a new warehouse-specific SKU."""

    name: str = Field(min_length=1, max_length=200)
    sku: str = Field(min_length=1, max_length=80)
    client_id: UUID
    category: Category
    warehouse: Warehouse
    min_stock_threshold: int = Field(default=0, ge=0)


class SKURead(APIModel):
    """SKU response with stock computed from movements rather than persisted."""

    id: int
    name: str
    sku: str
    client_id: UUID
    client_name: str
    category: Category
    warehouse: Warehouse
    min_stock_threshold: int
    current_stock: int


class SKUSummary(APIModel):
    """Nested SKU data returned alongside each movement."""

    id: int
    name: str
    sku: str
    client_id: UUID
    client_name: str
    category: Category
    warehouse: Warehouse
    min_stock_threshold: int


class SKUUpdate(APIModel):
    """Threshold is mutable; client_id is accepted only to return the documented conflict."""

    min_stock_threshold: int | None = Field(default=None, ge=0)
    client_id: UUID | None = None

    @model_validator(mode="after")
    def require_one_field(self) -> Self:
        if self.min_stock_threshold is None and self.client_id is None:
            raise ValueError("at least one update field is required")
        return self


class ClientCreate(APIModel):
    display_name: str = Field(min_length=1, max_length=160)


class ClientUpdate(APIModel):
    display_name: str = Field(min_length=1, max_length=160)


class ClientRead(APIModel):
    client_id: UUID
    client_name: str


class InventoryDiscrepancyCreate(APIModel):
    stock_exit_id: int = Field(gt=0)
    quantity_delta: int

    @model_validator(mode="after")
    def require_nonzero_delta(self) -> Self:
        if self.quantity_delta == 0:
            raise ValueError("quantity_delta must not be zero")
        return self


class InventoryDiscrepancyRead(APIModel):
    id: int
    stock_exit_id: int
    sku_id: int
    warehouse: Warehouse
    client_id: UUID
    quantity_delta: int
    source: Literal["manual", "feed"]
    detected_at: datetime
    created_by_user_uuid: str | None


class StockEntryCreate(APIModel):
    """A positive goods receipt at the referenced SKU's warehouse."""

    sku_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    reference: str = Field(min_length=1, max_length=120)
    warehouse: Warehouse


class StockEntryRead(StockEntryCreate):
    """Persisted inbound movement with server-owned audit fields."""

    id: int
    created_at: datetime
    user_uuid: str


class StockExitCreate(APIModel):
    """A dispatch or loss whose tracking fields agree with the exit type."""

    sku_id: int = Field(gt=0)
    quantity: int = Field(gt=0)
    exit_type: ExitType
    tracking_number: str | None = Field(default=None, min_length=1, max_length=120)
    warehouse: Warehouse

    @model_validator(mode="after")
    def validate_tracking_rule(self) -> Self:
        """Keep dispatch/loss semantics valid before opening a transaction."""
        if self.exit_type == ExitType.DISPATCH and self.tracking_number is None:
            raise ValueError("tracking_number is required for dispatch exits")
        if self.exit_type == ExitType.LOSS and self.tracking_number is not None:
            raise ValueError("tracking_number must be null for loss exits")
        return self


class StockExitRead(StockExitCreate):
    """Persisted outbound movement with server-owned audit fields."""

    id: int
    created_at: datetime
    user_uuid: str


class MovementRead(APIModel):
    """One normalized inbound/outbound timeline row with its SKU included."""

    id: int
    movement_type: Literal["inbound", "outbound"]
    sku_id: int
    quantity: int
    reference: str | None
    exit_type: ExitType | None
    tracking_number: str | None
    warehouse: Warehouse
    created_at: datetime
    user_uuid: str
    sku: SKUSummary


class ProductPage(APIModel):
    """Bounded product-list response with total-count metadata."""

    items: list[SKURead]
    total: int
    limit: int
    offset: int


class MovementPage(APIModel):
    """Bounded reverse-chronological movement response."""

    items: list[MovementRead]
    total: int
    limit: int
    offset: int


class HealthRead(APIModel):
    """Safe readiness response without connection or credential detail."""

    status: Literal["ok"]
    database: Literal["ok"]
