"""Celery consumers, retry policy, and dead-letter routing for DEV-55."""

from __future__ import annotations

import logging
import os
import time
from typing import Any, NoReturn
from uuid import uuid4

from celery import Task
from sqlmodel import Session

from ...celery_app import celery_app
from ...core.config import get_settings
from ...db.session import get_engine
from ..rfp.errors import RetryableRfpProcessingError
from ..rfp.processor import process_rfp_ticket
from .repository import TaskRepository

logger = logging.getLogger(__name__)
MAX_TOTAL_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (1, 2)


class TaskExecutionFailed(RuntimeError):
    """Safe terminal error stored in Celery without leaking the originating exception."""


def _log(task_id: str, operation: str, attempt: int, status: str, started: float, error: str | None = None) -> None:
    logger.info(
        "async_task task_id=%s operation=%s attempt=%s status=%s duration_ms=%s error=%s",
        task_id,
        operation,
        attempt,
        status,
        max(0, int((time.monotonic() - started) * 1000)),
        error or "none",
    )


def _terminal_failure(
    *,
    task_id: str,
    operation: str,
    entity_id: str | None,
    attempt: int,
    started: float,
    error_code: str,
    error_message: str,
) -> NoReturn:
    with Session(get_engine()) as session:
        failure, created = TaskRepository(session).record_failure(
            task_id=task_id,
            operation=operation,
            entity_id=entity_id,
            attempt=attempt,
            error_code=error_code,
            error_message=error_message,
        )
    if created:
        record_dead_letter.apply_async(args=[failure.id], queue="dead_letter")
    _log(task_id, operation, attempt, "failure", started, error_message)
    raise TaskExecutionFailed(error_message)


def _retry_or_fail(
    task: Task,
    *,
    task_id: str,
    operation: str,
    entity_id: str | None,
    attempt: int,
    started: float,
    error_code: str,
    error_message: str,
) -> NoReturn:
    if attempt >= MAX_TOTAL_ATTEMPTS:
        _terminal_failure(
            task_id=task_id,
            operation=operation,
            entity_id=entity_id,
            attempt=attempt,
            started=started,
            error_code=error_code,
            error_message=error_message,
        )
    countdown = RETRY_DELAYS_SECONDS[attempt - 1]
    _log(task_id, operation, attempt, "retry", started, error_message)
    raise task.retry(exc=TaskExecutionFailed(error_message), countdown=countdown, max_retries=3)


@celery_app.task(bind=True, name="trackflow.rfp.process", max_retries=3)  # type: ignore[untyped-decorator]
def process_rfp_task(task: Task, ticket_id: str) -> dict[str, str]:
    started = time.monotonic()
    attempt = int(task.request.retries) + 1
    try:
        status = process_rfp_ticket(ticket_id, get_settings())
    except RetryableRfpProcessingError:
        _retry_or_fail(
            task,
            task_id=ticket_id,
            operation="rfp_processing",
            entity_id=ticket_id,
            attempt=attempt,
            started=started,
            error_code="RFP_PROCESSING_FAILED",
            error_message="RFP processing failed after three attempts.",
        )
    except Exception:
        _terminal_failure(
            task_id=ticket_id,
            operation="rfp_processing",
            entity_id=ticket_id,
            attempt=attempt,
            started=started,
            error_code="RFP_PROCESSING_INVALID",
            error_message="RFP processing could not be completed.",
        )
    _log(ticket_id, "rfp_processing", attempt, "success", started)
    return {"ticket_id": ticket_id, "ticket_status": status}


def _run_dev55_failure(task: Task) -> None:
    task_id = str(task.request.id or uuid4())
    attempt = int(task.request.retries) + 1
    _retry_or_fail(
        task,
        task_id=task_id,
        operation="dev55_demo_failure",
        entity_id=None,
        attempt=attempt,
        started=time.monotonic(),
        error_code="DEV55_DEMO_FAILURE",
        error_message="DEV55_DEMO_FAILURE",
    )


dev55_failure_task: Any = None
if os.environ.get("APP_ENV", "local").strip().lower() != "production":
    dev55_failure_task = celery_app.task(
        bind=True,
        name="trackflow.dev55.failure",
        max_retries=3,
    )(_run_dev55_failure)


@celery_app.task(name="trackflow.dead_letter.record")  # type: ignore[untyped-decorator]
def record_dead_letter(failure_id: str) -> dict[str, str]:
    with Session(get_engine()) as session:
        TaskRepository(session).mark_dead_lettered(failure_id)
    return {"failure_id": failure_id, "status": "dead_lettered"}
