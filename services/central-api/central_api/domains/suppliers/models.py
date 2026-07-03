"""SQLModel persistence and database invariants for suppliers."""

from datetime import UTC, datetime
from typing import ClassVar
from uuid import uuid4

from sqlalchemy import JSON, CheckConstraint, Column, DateTime, Float, Index, String, Text, UniqueConstraint
from sqlalchemy.sql.schema import SchemaItem
from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(UTC)


class Supplier(SQLModel, table=True):
    __tablename__ = "suppliers"
    __table_args__: ClassVar[tuple[SchemaItem, ...]] = (
        CheckConstraint("country IN ('USA', 'Spain')", name="ck_suppliers_country"),
        CheckConstraint("currency IN ('USD', 'EUR')", name="ck_suppliers_currency"),
        CheckConstraint(
            "(country = 'USA' AND currency = 'USD') OR (country = 'Spain' AND currency = 'EUR')",
            name="ck_suppliers_country_currency",
        ),
        CheckConstraint("status IN ('active', 'suspended')", name="ck_suppliers_status"),
        CheckConstraint("rate_per_shipment > 0", name="ck_suppliers_positive_rate"),
        CheckConstraint(
            "jsonb_array_length(categories::jsonb) > 0 AND "
            "categories::jsonb <@ "
            "'[\"carrier_last_mile\", \"carrier_international\", \"warehouse_supplies\", "
            "\"packaging_materials\", \"reverse_logistics\", \"fleet_maintenance\", "
            "\"it_and_wms_software\", \"cleaning_and_facilities\"]'::jsonb",
            name="ck_suppliers_categories",
        ),
        UniqueConstraint("name", "country", name="uq_suppliers_name_country"),
        Index("ix_suppliers_country_name", "country", "name"),
        Index("ix_suppliers_status", "status"),
    )

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True, max_length=36)
    name: str = Field(sa_column=Column(String(160), nullable=False))
    country: str = Field(sa_column=Column(String(16), nullable=False))
    categories: list[str] = Field(sa_column=Column(JSON, nullable=False))
    rate_per_shipment: float = Field(sa_column=Column(Float, nullable=False))
    currency: str = Field(sa_column=Column(String(3), nullable=False))
    rate_updated_at: datetime = Field(
        default_factory=utc_now, sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    status: str = Field(sa_column=Column(String(16), nullable=False))
    service_zone: str | None = Field(default=None, sa_column=Column(String(200), nullable=True))
    contact_email: str | None = Field(default=None, sa_column=Column(String(320), nullable=True))
    notes: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
