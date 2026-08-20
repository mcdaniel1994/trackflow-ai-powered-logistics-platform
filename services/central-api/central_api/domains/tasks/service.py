"""Owner-scoped projection of Celery state into the DEV-55 API contract."""

from dataclasses import dataclass

from celery.exceptions import CeleryError
from celery.result import AsyncResult
from redis.exceptions import RedisError
from sqlmodel import Session

from ...celery_app import celery_app
from ..rfp.repository import RfpRepository
from .repository import TaskRepository
from .schemas import TaskStatusRead


@dataclass
class TaskStatusError(Exception):
    status_code: int
    detail: str


_STATE_MAP = {
    "PENDING": "pending",
    "RECEIVED": "pending",
    "RETRY": "pending",
    "STARTED": "started",
    "SUCCESS": "success",
    "FAILURE": "failure",
    "REVOKED": "failure",
    "IGNORED": "failure",
    "REJECTED": "failure",
}


class TaskStatusService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.rfp_repository = RfpRepository(session)
        self.task_repository = TaskRepository(session)

    def get(self, task_id: str, owner_user_uuid: str) -> TaskStatusRead:
        ticket = self.rfp_repository.get_for_owner(task_id, owner_user_uuid)
        if ticket is None:
            raise TaskStatusError(404, "Task not found.")
        if self.task_repository.failure_for_task(task_id) is not None:
            return TaskStatusRead(task_id=task_id, status="failure", result=None)

        try:
            result = AsyncResult(task_id, app=celery_app)
            status = _STATE_MAP.get(result.state, "pending")
        except (CeleryError, RedisError, OSError):
            raise TaskStatusError(503, "The task queue is unavailable right now.") from None
        safe_result: dict[str, str] | None = None
        if status == "success":
            safe_result = {"ticket_id": ticket.id, "ticket_status": ticket.status}
        return TaskStatusRead(task_id=task_id, status=status, result=safe_result)
