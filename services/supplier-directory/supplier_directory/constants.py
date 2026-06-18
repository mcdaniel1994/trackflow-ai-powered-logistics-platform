"""Shared supplier directory constants."""

from __future__ import annotations

VALID_CATEGORIES: tuple[str, ...] = (
    "carrier_last_mile",
    "carrier_international",
    "warehouse_supplies",
    "packaging_materials",
    "reverse_logistics",
    "fleet_maintenance",
    "it_and_wms_software",
    "cleaning_and_facilities",
)

VALID_STATUSES: tuple[str, ...] = ("active", "suspended")

COUNTRY_CURRENCY: dict[str, str] = {
    "USA": "USD",
    "Spain": "EUR",
}

VALID_COUNTRIES = tuple(COUNTRY_CURRENCY.keys())
VALID_CURRENCIES = tuple(COUNTRY_CURRENCY.values())
