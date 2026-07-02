"""Bounded incident queries and row-locked lifecycle writes."""

from typing import cast

from sqlalchemy import Table, func
from sqlalchemy import select as sa_select
from sqlmodel import Session, select

from .models import Incident

incident_table = cast(Table, Incident.__table__)  # type: ignore[attr-defined]


class IncidentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, incident: Incident) -> None:
        self.session.add(incident)

    def list(
        self,
        *,
        status: str | None,
        origin: str | None,
        branch: str | None,
        category: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Incident], int]:
        filters = []
        for column, value in (
            (incident_table.c.status, status),
            (incident_table.c.origin, origin),
            (incident_table.c.branch, branch),
            (incident_table.c.category, category),
        ):
            if value is not None:
                filters.append(column == value)
        statement = (
            select(Incident)
            .where(*filters)
            .order_by(incident_table.c.created_at.desc(), incident_table.c.id.desc())
            .limit(limit)
            .offset(offset)
        )
        count_statement = sa_select(func.count()).select_from(incident_table).where(*filters)
        return list(self.session.exec(statement).all()), int(self.session.scalar(count_statement) or 0)

    def get(self, incident_id: int) -> Incident | None:
        return self.session.get(Incident, incident_id)

    def get_for_update(self, incident_id: int) -> Incident | None:
        return self.session.exec(
            select(Incident).where(incident_table.c.id == incident_id).with_for_update()
        ).one_or_none()

    def grouped_counts(self, field: str) -> dict[str, int]:
        column = incident_table.c[field]
        rows = self.session.execute(sa_select(column, func.count()).group_by(column)).all()
        return {str(value): int(count) for value, count in rows}

    def count(self) -> int:
        return int(self.session.scalar(sa_select(func.count()).select_from(incident_table)) or 0)

    def import_key_exists(self, import_key_hash: str) -> bool:
        statement = sa_select(incident_table.c.id).where(incident_table.c.import_key_hash == import_key_hash)
        return self.session.scalar(statement) is not None

