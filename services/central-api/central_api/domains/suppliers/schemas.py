"""Supplier API schemas preserving the existing Back Office contract."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .constants import COUNTRY_CURRENCY, VALID_CATEGORIES, VALID_STATUSES


def blank_to_none(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


class SupplierCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=160)
    country: str
    categories: list[str] = Field(min_length=1)
    rate_per_shipment: float = Field(gt=0)
    currency: str
    status: str
    service_zone: str | None = None
    contact_email: str | None = None
    notes: str | None = None

    @field_validator("country")
    @classmethod
    def country_valid(cls, value: str) -> str:
        if value not in COUNTRY_CURRENCY:
            raise ValueError("Country must be USA or Spain")
        return value

    @field_validator("categories")
    @classmethod
    def categories_valid(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(value not in VALID_CATEGORIES for value in normalized):
            raise ValueError("Supplier category is not valid")
        return normalized

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str) -> str:
        if value not in VALID_STATUSES:
            raise ValueError("Status must be active or suspended")
        return value

    @field_validator("service_zone", "contact_email", "notes", mode="before")
    @classmethod
    def optional_text(cls, value: Any) -> Any:
        return blank_to_none(value)

    @model_validator(mode="after")
    def currency_matches_country(self) -> "SupplierCreate":
        if self.currency != COUNTRY_CURRENCY[self.country]:
            raise ValueError(f"{self.country} suppliers must use {COUNTRY_CURRENCY[self.country]}")
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
    rate_per_shipment: float = Field(gt=0)


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    status: str

    @field_validator("status")
    @classmethod
    def status_valid(cls, value: str) -> str:
        if value not in VALID_STATUSES:
            raise ValueError("Status must be active or suspended")
        return value
