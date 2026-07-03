"""Idempotently copy suppliers from a TinyDB JSON snapshot into PostgreSQL."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import Session

from central_api.db.session import get_engine
from central_api.domains.suppliers.schemas import SupplierCreate
from central_api.domains.suppliers.service import SupplierService


def read_records(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    table = data.get("suppliers", {})
    if not isinstance(table, dict):
        raise ValueError("TinyDB suppliers table must be an object")
    return [dict(record) for record in table.values()]


def import_records(path: Path, session: Session) -> tuple[int, int]:
    inserted = skipped = 0
    service = SupplierService(session)
    for record in read_records(path):
        payload = SupplierCreate.model_validate(
            {key: value for key, value in record.items() if key not in {"id", "rate_updated_at"}}
        )
        if service.repository.find_identity(payload.name, payload.country):
            skipped += 1
            continue
        service.create(
            payload,
            supplier_id=str(record["id"]),
            rate_updated_at=datetime.fromisoformat(str(record["rate_updated_at"]).replace("Z", "+00:00")),
        )
        inserted += 1
    return inserted, skipped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshot", type=Path)
    args = parser.parse_args(argv)
    with Session(get_engine()) as session:
        inserted, skipped = import_records(args.snapshot, session)
    print(f"Inserted {inserted}; skipped {skipped}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
