"""Business rules layer for the supplier directory."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from .models import RateUpdate, StatusUpdate, SupplierContact, SupplierCreate, SupplierPublic
from .repository import SupplierRepository


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SupplierService:
    def __init__(self, repository: SupplierRepository) -> None:
        self.repository = repository

    def seed_if_empty(self, suppliers: Iterable[dict[str, object]]) -> int:
        if self.repository.count() > 0:
            return 0
        return self.seed_suppliers(suppliers)

    def seed_suppliers(self, suppliers: Iterable[dict[str, object]]) -> int:
        inserted = 0

        for supplier in suppliers:
            payload = SupplierCreate.model_validate(supplier)
            if self.repository.find_by_identity(payload.name, payload.country):
                continue

            record = payload.model_dump()
            record["rate_updated_at"] = _now_iso()
            self.repository.insert_supplier(record)
            inserted += 1

        return inserted

    def list_suppliers(self, country: str | None = None, category: str | None = None) -> list[SupplierPublic]:
        return [
            self._to_public(record)
            for record in self.repository.list_suppliers(country=country, category=category)
        ]

    def get_supplier(self, supplier_id: str) -> SupplierPublic | None:
        record = self.repository.get_supplier(supplier_id)
        return self._to_public(record) if record else None

    def get_supplier_contact(self, supplier_id: str) -> SupplierContact | None:
        record = self.repository.get_supplier(supplier_id)
        if not record:
            return None
        return SupplierContact(id=str(record["id"]), contact_email=record.get("contact_email"))

    def create_supplier(self, payload: SupplierCreate) -> SupplierPublic:
        record = payload.model_dump()
        record["rate_updated_at"] = _now_iso()
        return self._to_public(self.repository.insert_supplier(record))

    def update_rate(self, supplier_id: str, payload: RateUpdate) -> SupplierPublic | None:
        record = self.repository.update_supplier(
            supplier_id,
            {
                "rate_per_shipment": payload.rate_per_shipment,
                "rate_updated_at": _now_iso(),
            },
        )
        return self._to_public(record) if record else None

    def update_status(self, supplier_id: str, payload: StatusUpdate) -> SupplierPublic | None:
        record = self.repository.update_supplier(supplier_id, {"status": payload.status})
        return self._to_public(record) if record else None

    def delete_supplier(self, supplier_id: str) -> bool:
        return self.repository.delete_supplier(supplier_id)

    def _to_public(self, record: dict[str, object]) -> SupplierPublic:
        contact_email = record.get("contact_email")
        return SupplierPublic.model_validate(
            {
                "id": record["id"],
                "name": record["name"],
                "country": record["country"],
                "categories": record["categories"],
                "rate_per_shipment": record["rate_per_shipment"],
                "currency": record["currency"],
                "rate_updated_at": record["rate_updated_at"],
                "status": record["status"],
                "service_zone": record.get("service_zone"),
                "notes": record.get("notes"),
                "has_contact_email": bool(str(contact_email).strip()) if contact_email else False,
            }
        )
