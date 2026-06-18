"""Pydantic models and validation for the supplier directory."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import COUNTRY_CURRENCY, VALID_CATEGORIES, VALID_CURRENCIES, VALID_STATUSES


def _blank_to_none(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return value


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    country: str
    categories: list[str] = Field(min_length=1)
    rate_per_shipment: float
    currency: str
    status: str
    service_zone: str | None = None
    contact_email: str | None = None
    notes: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Supplier name is required")
        return value

    @field_validator("country")
    @classmethod
    def validate_country(cls, value: str) -> str:
        if value not in COUNTRY_CURRENCY:
            raise ValueError("Country must be USA or Spain")
        return value

    @field_validator("categories")
    @classmethod
    def validate_categories(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() if isinstance(value, str) else value for value in values]
        if not normalized:
            raise ValueError("At least one supplier category is required")

        invalid = [value for value in normalized if value not in VALID_CATEGORIES]
        if invalid:
            raise ValueError("Supplier category is not valid")

        return normalized

    @field_validator("rate_per_shipment")
    @classmethod
    def validate_rate(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Rate per shipment must be greater than zero")
        return value

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        if value not in VALID_CURRENCIES:
            raise ValueError("Currency must be USD or EUR")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VALID_STATUSES:
            raise ValueError("Status must be active or suspended")
        return value

    @field_validator("service_zone", "contact_email", "notes", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> Any:
        return _blank_to_none(value)

    @model_validator(mode="after")
    def validate_currency_matches_country(self) -> "SupplierCreate":
        expected = COUNTRY_CURRENCY[self.country]
        if self.currency != expected:
            raise ValueError(f"{self.country} suppliers must use {expected}")
        return self


class SupplierPublic(BaseModel):
    id: str
    name: str
    country: str
    categories: list[str]
    rate_per_shipment: float
    currency: str
    rate_updated_at: datetime
    status: str
    service_zone: str | None = None
    notes: str | None = None
    has_contact_email: bool


class SupplierContact(BaseModel):
    id: str
    contact_email: str | None = None


class RateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rate_per_shipment: float

    @field_validator("rate_per_shipment")
    @classmethod
    def validate_rate(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Rate per shipment must be greater than zero")
        return value


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VALID_STATUSES:
            raise ValueError("Status must be active or suspended")
        return value
