"""DEV-55 queue boundary, status projection, retry, and durable DLQ evidence."""

from __future__ import annotations

import logging
import time
from typing import Any

import pytest
from fastapi.testclient import TestClient
from kombu.exceptions import OperationalError
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.core.config import Settings
from central_api.domains.rfp import processor as rfp_processor
from central_api.domains.rfp import service as rfp_service
from central_api.domains.rfp.models import RfpTicket
from central_api.domains.rfp.repository import RfpRepository
from central_api.domains.rfp.service import RfpError, RfpService
from central_api.domains.tasks import celery_tasks
from central_api.domains.tasks import dispatcher as task_dispatcher
from central_api.domains.tasks import service as task_service
from central_api.domains.tasks.models import AsyncTaskFailure

OWNER = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER = "22222222-2222-4222-8222-222222222222"


def _seed_ticket(engine: Engine, *, owner: str = OWNER, status: str = "analyzing") -> str:
    with Session(engine) as session:
        ticket = RfpRepository(session).add_ticket(
            RfpTicket(
                rfp_id=f"RFP-DEV55-{owner[:4]}-{status}",
                status=status,
                owner_user_uuid=owner,
                markdown_text="private proposal body",
            )
        )
        return ticket.id


class _Result:
    def __init__(self, state: str) -> None:
        self.state = state


@pytest.mark.parametrize(
    ("celery_state", "expected"),
    [
        ("PENDING", "pending"),
        ("RETRY", "pending"),
        ("STARTED", "started"),
        ("SUCCESS", "success"),
        ("FAILURE", "failure"),
        ("REVOKED", "failure"),
    ],
)
def test_task_status_maps_celery_states_with_safe_results(
    client: TestClient,
    engine: Engine,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    celery_state: str,
    expected: str,
) -> None:
    task_id = _seed_ticket(engine)
    monkeypatch.setattr(task_service, "AsyncResult", lambda *_args, **_kwargs: _Result(celery_state))

    response = client.get(f"/tasks/{task_id}", headers=auth_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == expected
    assert body["task_id"] == task_id
    if expected == "success":
        assert body["result"] == {"ticket_id": task_id, "ticket_status": "analyzing"}
    else:
        assert body["result"] is None
    assert "private proposal body" not in response.text


def test_task_status_requires_authentication_and_owner(
    client: TestClient,
    engine: Engine,
    auth_headers: dict[str, str],
) -> None:
    task_id = _seed_ticket(engine, owner=OTHER_OWNER)
    assert client.get(f"/tasks/{task_id}").status_code == 401
    assert client.get(f"/tasks/{task_id}", headers=auth_headers).status_code == 404
    assert client.get("/tasks/does-not-exist", headers=auth_headers).status_code == 404


def test_dispatcher_sends_only_ticket_uuid_and_reuses_it_as_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    task_id = "00000000-0000-4000-8000-000000000055"
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        task_dispatcher.process_rfp_task,
        "apply_async",
        lambda **kwargs: calls.append(kwargs),
    )

    task_dispatcher.enqueue_rfp_processing(task_id)

    assert calls == [{"args": [task_id], "task_id": task_id, "queue": "rfp"}]


def test_broker_failure_compensates_ticket_before_realtime_publish(
    engine: Engine,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    published: list[dict[str, object]] = []

    class Bus:
        def publish(self, _topic: str, _event: str, data: dict[str, object]) -> None:
            published.append(data)

    monkeypatch.setattr(rfp_service, "pdf_to_markdown", lambda _data: "converted markdown")

    def unavailable(_ticket_id: str) -> None:
        raise OperationalError("broker unavailable")

    monkeypatch.setattr(rfp_service, "enqueue_rfp_processing", unavailable)
    configured = settings.model_copy(update={"rfp_enabled": True, "openai_api_key": "test-key"})
    with Session(engine) as session:
        service = RfpService(configured, session, realtime_bus=Bus())  # type: ignore[arg-type]
        with pytest.raises(RfpError) as exc_info:
            service.create_from_upload(
                owner_user_uuid=OWNER,
                operator_jurisdiction="US",
                filename="rfp.pdf",
                content_type="application/pdf",
                data=b"%PDF",
            )
        assert exc_info.value.status_code == 503
        assert session.exec(select(RfpTicket)).all() == []
    assert published == []


class _RetryRaised(Exception):
    pass


class _FakeTask:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def retry(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)
        raise _RetryRaised


@pytest.mark.parametrize(("attempt", "countdown"), [(1, 1), (2, 2)])
def test_retry_countdown_increases(attempt: int, countdown: int) -> None:
    task = _FakeTask()
    with pytest.raises(_RetryRaised):
        celery_tasks._retry_or_fail(  # type: ignore[arg-type]
            task,
            task_id="00000000-0000-4000-8000-000000000001",
            operation="rfp_processing",
            entity_id=None,
            attempt=attempt,
            started=time.monotonic(),
            error_code="SAFE",
            error_message="safe failure",
        )
    assert task.calls[0]["countdown"] == countdown
    assert task.calls[0]["max_retries"] == 3


def test_third_failure_is_idempotently_recorded_and_dead_lettered(
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id = _seed_ticket(engine)
    markers: list[tuple[list[str], str]] = []
    monkeypatch.setattr(celery_tasks, "get_engine", lambda: engine)
    monkeypatch.setattr(
        celery_tasks.record_dead_letter,
        "apply_async",
        lambda args, queue: markers.append((args, queue)),
    )

    for _ in range(2):
        with pytest.raises(celery_tasks.TaskExecutionFailed):
            celery_tasks._terminal_failure(
                task_id=ticket_id,
                operation="rfp_processing",
                entity_id=ticket_id,
                attempt=3,
                started=time.monotonic(),
                error_code="RFP_PROCESSING_FAILED",
                error_message="RFP processing failed after three attempts.",
            )

    with Session(engine) as session:
        failures = session.exec(select(AsyncTaskFailure)).all()
        ticket = session.get(RfpTicket, ticket_id)
        assert len(failures) == 1
        assert failures[0].attempt == 3
        assert ticket is not None and ticket.status == "failed"
        failure_id = failures[0].id
    assert markers == [([failure_id], "dead_letter")]

    result = celery_tasks.record_dead_letter.run(failure_id)
    assert result == {"failure_id": failure_id, "status": "dead_lettered"}
    with Session(engine) as session:
        assert session.get(AsyncTaskFailure, failure_id).dead_lettered_at is not None  # type: ignore[union-attr]


def test_processor_resumes_from_persisted_stage_and_is_idempotent(
    engine: Engine,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ticket_id = _seed_ticket(engine, status="drafting")
    calls: list[str] = []
    configured = settings.model_copy(
        update={"rfp_enabled": True, "openai_api_key": "openai", "deepseek_api_key": "deepseek"}
    )
    monkeypatch.setattr(rfp_processor, "build_rag_config", lambda _settings: object())
    monkeypatch.setattr(rfp_processor, "run_intake_for_ticket", lambda *_args, **_kwargs: calls.append("intake"))

    def generation(ticket: str, *_args: object, **_kwargs: object) -> None:
        calls.append("generation")
        with Session(engine) as session:
            persisted = session.get(RfpTicket, ticket)
            assert persisted is not None
            persisted.status = "under_evaluation"
            session.add(persisted)
            session.commit()

    def approval(ticket: str, *_args: object, **_kwargs: object) -> None:
        calls.append("approval")
        with Session(engine) as session:
            persisted = session.get(RfpTicket, ticket)
            assert persisted is not None
            persisted.status = "waiting_for_approval"
            session.add(persisted)
            session.commit()

    monkeypatch.setattr(rfp_processor, "run_generation_for_ticket", generation)
    monkeypatch.setattr(rfp_processor, "start_ticket_approval", approval)

    assert rfp_processor.process_rfp_ticket(ticket_id, configured) == "waiting_for_approval"
    assert rfp_processor.process_rfp_ticket(ticket_id, configured) == "waiting_for_approval"
    assert calls == ["generation", "approval"]


def test_task_logs_only_sanitized_fields(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    celery_tasks._log(
        "00000000-0000-4000-8000-000000000001",
        "rfp_processing",
        1,
        "retry",
        time.monotonic(),
        "safe failure",
    )
    text = caplog.text
    assert "safe failure" in text
    assert "private proposal body" not in text
    assert "provider payload" not in text
