"""TinyDB persistence for suppliers."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from tinydb import Query, TinyDB


def _identity(name: str, country: str) -> tuple[str, str]:
    return (name.strip().casefold(), country.strip().casefold())


class SupplierRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(self.db_path))
        self.table = self.db.table("suppliers")

    def close(self) -> None:
        self.db.close()

    def count(self) -> int:
        return len(self.table)

    def list_suppliers(self, country: str | None = None, category: str | None = None) -> list[dict[str, object]]:
        records = [dict(record) for record in self.table.all()]

        if country:
            records = [record for record in records if record.get("country") == country]

        if category:
            records = [
                record
                for record in records
                if category in (record.get("categories") or [])
            ]

        return sorted(records, key=lambda record: (str(record.get("country")), str(record.get("name"))))

    def get_supplier(self, supplier_id: str) -> dict[str, object] | None:
        supplier = Query()
        record = self.table.get(supplier.id == supplier_id)
        return dict(record) if record else None

    def find_by_identity(self, name: str, country: str) -> dict[str, object] | None:
        needle = _identity(name, country)
        for record in self.table.all():
            if _identity(str(record.get("name", "")), str(record.get("country", ""))) == needle:
                return dict(record)
        return None

    def insert_supplier(self, data: dict[str, object]) -> dict[str, object]:
        record = dict(data)
        record["id"] = str(uuid4())
        self.table.insert(record)
        return record

    def update_supplier(self, supplier_id: str, changes: dict[str, object]) -> dict[str, object] | None:
        supplier = Query()
        updated = self.table.update(changes, supplier.id == supplier_id)
        if not updated:
            return None
        return self.get_supplier(supplier_id)

    def delete_supplier(self, supplier_id: str) -> bool:
        supplier = Query()
        deleted = self.table.remove(supplier.id == supplier_id)
        return bool(deleted)
