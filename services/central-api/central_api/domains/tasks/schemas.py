"""Public API contracts for Celery task status."""

from typing import Literal

from pydantic import BaseModel


class TaskStatusRead(BaseModel):
    task_id: str
    status: Literal["pending", "started", "success", "failure"]
    result: dict[str, str] | None = None
