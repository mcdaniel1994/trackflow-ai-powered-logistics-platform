"""Incident lifecycle, persistence, and safe failure translation."""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session
from trackflow_incidents import (
    BRANCH_VALUES,
    CATEGORY_VALUES,
    ORIGIN_VALUES,
    STATUS_VALUES,
    Branch,
    IncidentCategory,
    IncidentOrigin,
    IncidentStatus,
)

from .models import Incident
from .repository import IncidentRepository
from .schemas import IncidentCreate, IncidentPage, IncidentRead, IncidentStatusUpdate, IncidentSummary

logger = logging.getLogger(__name__)

ALLOWED_TRANSITIONS = {
    IncidentStatus.OPEN: {IncidentStatus.IN_PROGRESS, IncidentStatus.DISCARDED},
    IncidentStatus.IN_PROGRESS: {IncidentStatus.RESOLVED, IncidentStatus.DISCARDED},
    IncidentStatus.RESOLVED: set(),
    IncidentStatus.DISCARDED: set(),
}


@dataclass
class IncidentError(Exception):
    status_code: int
    code: str
    message: str
    field: str | None = None


class IncidentService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.repository = IncidentRepository(session)

    def _persistence_failure(self, operation: str, exc: SQLAlchemyError) -> IncidentError:
        self.session.rollback()
        logger.error("incident_database_failure operation=%s error_type=%s", operation, type(exc).__name__)
        return IncidentError(503, "SERVICE_UNAVAILABLE", "Incident service temporarily unavailable.")

    @staticmethod
    def _read(incident: Incident) -> IncidentRead:
        if incident.id is None:
            raise RuntimeError("Persisted incident is missing its primary key")
        return IncidentRead.model_validate(incident)

    def create(self, payload: IncidentCreate, reporter_uuid: str) -> IncidentRead:
        incident = Incident(
            **payload.model_dump(mode="json"),
            status=IncidentStatus.OPEN.value,
            created_by_user_uuid=reporter_uuid,
        )
        try:
            self.repository.add(incident)
            self.session.commit()
            self.session.refresh(incident)
        except SQLAlchemyError as exc:
            raise self._persistence_failure("create", exc) from exc
        return self._read(incident)

    def list(
        self,
        *,
        status: IncidentStatus | None,
        origin: IncidentOrigin | None,
        branch: Branch | None,
        category: IncidentCategory | None,
        limit: int,
        offset: int,
    ) -> IncidentPage:
        try:
            rows, total = self.repository.list(
                status=status.value if status else None,
                origin=origin.value if origin else None,
                branch=branch.value if branch else None,
                category=category.value if category else None,
                limit=limit,
                offset=offset,
            )
        except SQLAlchemyError as exc:
            raise self._persistence_failure("list", exc) from exc
        return IncidentPage(items=[self._read(row) for row in rows], total=total, limit=limit, offset=offset)

    def get(self, incident_id: int) -> IncidentRead:
        try:
            incident = self.repository.get(incident_id)
        except SQLAlchemyError as exc:
            raise self._persistence_failure("get", exc) from exc
        if incident is None:
            raise IncidentError(404, "INCIDENT_NOT_FOUND", "Incident not found.")
        return self._read(incident)

    def update_status(self, incident_id: int, payload: IncidentStatusUpdate) -> IncidentRead:
        try:
            incident = self.repository.get_for_update(incident_id)
            if incident is None:
                raise IncidentError(404, "INCIDENT_NOT_FOUND", "Incident not found.")
            current = IncidentStatus(incident.status)
            if payload.status not in ALLOWED_TRANSITIONS[current]:
                raise IncidentError(
                    400,
                    "INVALID_STATUS_TRANSITION",
                    f"Status cannot change from {current.value} to {payload.status.value}.",
                    "status",
                )
            incident.status = payload.status.value
            incident.updated_at = datetime.now(UTC)
            self.session.add(incident)
            self.session.commit()
            self.session.refresh(incident)
        except IncidentError:
            self.session.rollback()
            raise
        except SQLAlchemyError as exc:
            raise self._persistence_failure("update_status", exc) from exc
        return self._read(incident)

    def summary(self) -> IncidentSummary:
        try:
            return IncidentSummary(
                total=self.repository.count(),
                by_status=self._filled_counts(STATUS_VALUES, self.repository.grouped_counts("status")),
                by_category=self._filled_counts(CATEGORY_VALUES, self.repository.grouped_counts("category")),
                by_origin=self._filled_counts(ORIGIN_VALUES, self.repository.grouped_counts("origin")),
                by_branch=self._filled_counts(BRANCH_VALUES, self.repository.grouped_counts("branch")),
            )
        except SQLAlchemyError as exc:
            raise self._persistence_failure("summary", exc) from exc

    @staticmethod
    def _filled_counts(values: tuple[str, ...], counts: dict[str, int]) -> dict[str, int]:
        return {value: counts.get(value, 0) for value in values}

