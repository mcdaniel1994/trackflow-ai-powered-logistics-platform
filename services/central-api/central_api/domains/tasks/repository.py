"""Persistence operations for asynchronous task failure evidence."""

from sqlmodel import Session, select

from ..rfp.models import RfpTicket, utc_now
from .models import AsyncTaskFailure


class TaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def failure_for_task(self, task_id: str) -> AsyncTaskFailure | None:
        return self.session.exec(
            select(AsyncTaskFailure).where(AsyncTaskFailure.task_id == task_id)
        ).one_or_none()

    def record_failure(
        self,
        *,
        task_id: str,
        operation: str,
        entity_id: str | None,
        attempt: int,
        error_code: str,
        error_message: str,
    ) -> tuple[AsyncTaskFailure, bool]:
        existing = self.failure_for_task(task_id)
        if existing is not None:
            return existing, False
        failure = AsyncTaskFailure(
            task_id=task_id,
            operation=operation,
            entity_id=entity_id,
            attempt=attempt,
            error_code=error_code,
            error_message=error_message,
        )
        self.session.add(failure)
        if entity_id is not None:
            ticket = self.session.get(RfpTicket, entity_id)
            if ticket is not None:
                ticket.status = "failed"
                ticket.updated_at = utc_now()
                self.session.add(ticket)
        self.session.commit()
        self.session.refresh(failure)
        return failure, True

    def mark_dead_lettered(self, failure_id: str) -> None:
        failure = self.session.get(AsyncTaskFailure, failure_id)
        if failure is None or failure.dead_lettered_at is not None:
            return
        failure.dead_lettered_at = utc_now()
        self.session.add(failure)
        self.session.commit()
