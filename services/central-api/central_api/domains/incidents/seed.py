"""Idempotent import of validated historical customer incidents."""

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlmodel import Session
from trackflow_incidents import LegacyCsvError, normalize_legacy_incident, parse_legacy_csv

from ...db.session import get_engine
from .models import Incident
from .repository import IncidentRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedResult:
    total_records: int
    inserted: int
    skipped: int
    invalid_records: int


def seed_incidents(path: Path, session: Session) -> SeedResult:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise LegacyCsvError("FILE_READ_ERROR", "CSV file could not be read.") from exc

    validation = parse_legacy_csv(data)
    repository = IncidentRepository(session)
    inserted = 0
    skipped = 0
    try:
        for row in validation.valid_rows:
            normalized = normalize_legacy_incident(row)
            if repository.import_key_exists(normalized.import_key_hash):
                skipped += 1
                continue
            repository.add(
                Incident(
                    title=normalized.title,
                    description=normalized.description,
                    category=normalized.category.value,
                    status=normalized.status.value,
                    origin=normalized.origin.value,
                    branch=normalized.branch.value,
                    created_at=normalized.created_at,
                    updated_at=normalized.updated_at,
                    created_by_user_uuid=None,
                    import_key_hash=normalized.import_key_hash,
                )
            )
            try:
                session.commit()
                inserted += 1
            except IntegrityError:
                # A concurrent or repeated importer may win the unique-key race.
                session.rollback()
                skipped += 1
        return SeedResult(validation.total_records, inserted, skipped, validation.invalid_records)
    except SQLAlchemyError:
        session.rollback()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed validated historical incidents into Central API.")
    parser.add_argument("csv_path", type=Path)
    args = parser.parse_args(argv)
    try:
        with Session(get_engine()) as session:
            result = seed_incidents(args.csv_path, session)
    except LegacyCsvError as exc:
        print(f"Import failed: {exc.code}")
        return 1
    print(
        f"Incident seed complete: inserted={result.inserted} skipped={result.skipped} "
        f"invalid={result.invalid_records} total={result.total_records}"
    )
    return 0


def entrypoint() -> None:
    raise SystemExit(main())

