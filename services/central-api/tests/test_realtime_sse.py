"""Phase 2 coverage for owner-scoped, model-free RFP notifications over SSE."""

from __future__ import annotations

import ast
import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request
from trackflow_auth import ACCESS_COOKIE_NAME  # type: ignore[import-untyped]

from central_api.core.config import Settings, get_settings
from central_api.domains.realtime.auth import RealtimePrincipal, authenticate_http_stream
from central_api.domains.realtime.bus import RealtimeBus, rfp_ticket_topic
from central_api.domains.realtime.router import (
    encode_sse_event,
    rfp_ticket_stream,
    stream_rfp_events,
)
from central_api.domains.realtime.schemas import RealtimeEvent
from central_api.domains.rfp.models import RfpTicket
from central_api.domains.rfp.service import RfpService


def _request(*, cookie: str | None = None, bearer: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", f"{ACCESS_COOKIE_NAME}={cookie}".encode()))
    if bearer:
        headers.append((b"authorization", f"Bearer {bearer}".encode()))
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "GET",
            "scheme": "https",
            "path": "/realtime/rfp/stream",
            "raw_path": b"/realtime/rfp/stream",
            "query_string": b"",
            "headers": headers,
            "client": ("127.0.0.1", 1234),
            "server": ("backoffice.forgehub.cloud", 443),
        }
    )


def test_sse_encoder_uses_named_event_id_and_compact_json() -> None:
    event = RealtimeEvent(
        event_id=7,
        event="rfp_ticket_created",
        data={"ticket_id": "ticket-1", "client_name": None},
    )
    assert encode_sse_event(event) == (
        b'id: 7\nevent: rfp_ticket_created\ndata: {"ticket_id":"ticket-1","client_name":null}\n\n'
    )


def test_endpoint_is_flag_gated_and_rejects_bearer_only(
    app: Any,
    client: TestClient,
    settings: Settings,
    token_factory: Any,
) -> None:
    assert client.get("/realtime/rfp/stream").status_code == 503
    enabled = settings.model_copy(update={"rfp_enabled": True})
    app.dependency_overrides[get_settings] = lambda: enabled

    assert client.get(
        "/realtime/rfp/stream",
        headers={"Authorization": f"Bearer {token_factory()}"},
    ).status_code == 401


def test_endpoint_headers_owner_isolation_and_nullable_payload(settings: Settings, token_factory: Any) -> None:
    async def scenario() -> None:
        enabled = settings.model_copy(update={"rfp_enabled": True})
        request = _request(cookie=token_factory())
        bus = RealtimeBus()
        response = await rfp_ticket_stream(request, enabled, bus)
        iterator = response.body_iterator.__aiter__()

        assert response.media_type == "text/event-stream"
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.headers["cache-control"] == "no-cache"
        assert response.headers["x-accel-buffering"] == "no"
        assert await anext(iterator) == b": connected\n\n"

        pending = asyncio.create_task(anext(iterator))
        bus.publish(rfp_ticket_topic("other-owner"), "rfp_ticket_created", {"ticket_id": "hidden"})
        await asyncio.sleep(0)
        assert pending.done() is False
        bus.publish(
            rfp_ticket_topic("11111111-1111-4111-8111-111111111111"),
            "rfp_ticket_created",
            {
                "ticket_id": "visible",
                "rfp_id": "RFP-VISIBLE",
                "client_name": None,
                "client_country": None,
                "services_requested": [],
                "status": "analyzing",
                "created_at": "2026-08-18T12:00:00Z",
            },
        )
        chunk = await asyncio.wait_for(pending, timeout=0.2)
        assert b'"ticket_id":"visible"' in chunk
        assert b'"client_name":null' in chunk
        assert b'"services_requested":[]' in chunk
        await iterator.aclose()
        assert bus.subscriber_count(rfp_ticket_topic("11111111-1111-4111-8111-111111111111")) == 0

    asyncio.run(scenario())


def test_stream_emits_keepalive_and_closes_at_token_expiry(settings: Settings, token_factory: Any) -> None:
    async def scenario() -> None:
        verified = authenticate_http_stream(
            _request(cookie=token_factory()),
            settings,
        )
        auth = RealtimePrincipal(verified.principal, datetime.now(UTC) + timedelta(milliseconds=80))
        bus = RealtimeBus()
        iterator = stream_rfp_events(bus, auth, keepalive_seconds=0.01)

        assert await anext(iterator) == b": connected\n\n"
        assert await asyncio.wait_for(anext(iterator), timeout=0.05) == b": keep-alive\n\n"
        while True:
            try:
                await asyncio.wait_for(anext(iterator), timeout=0.2)
            except StopAsyncIteration:
                break
        assert bus.subscriber_count(rfp_ticket_topic(auth.principal.user_id)) == 0

    asyncio.run(scenario())


def test_ticket_publication_occurs_after_commit_and_enqueue(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    committed = False
    sequence: list[str] = []
    published: list[tuple[str, str, dict[str, object]]] = []

    class Repository:
        def add_ticket(self, ticket: RfpTicket) -> RfpTicket:
            nonlocal committed
            committed = True
            sequence.append("persisted")
            return ticket

    class RecordingBus:
        def publish(self, topic: str, event: str, data: dict[str, object]) -> RealtimeEvent:
            assert committed is True
            sequence.append("published")
            published.append((topic, event, data))
            return RealtimeEvent(event_id=1, event=event, data=data)

    monkeypatch.setattr("central_api.domains.rfp.service.pdf_to_markdown", lambda _data: "Readable proposal text.")
    monkeypatch.setattr(
        "central_api.domains.rfp.service.enqueue_rfp_processing",
        lambda _ticket_id: sequence.append("enqueued"),
    )
    configured = settings.model_copy(update={"rfp_enabled": True, "openai_api_key": "configured-for-gate-only"})
    service = RfpService(configured, object(), realtime_bus=RecordingBus())  # type: ignore[arg-type]
    service.repository = Repository()  # type: ignore[assignment]
    result = service.create_from_upload(
        owner_user_uuid="owner-1",
        operator_jurisdiction="US",
        filename="rfp.pdf",
        content_type="application/pdf",
        data=b"%PDF",
    )

    assert result.status == "analyzing"
    assert result.task_id == result.id
    assert sequence == ["persisted", "enqueued", "published"]
    assert published[0][0] == "rfp.tickets.owner-1"
    assert published[0][1] == "rfp_ticket_created"
    assert published[0][2]["client_name"] is None
    assert published[0][2]["client_country"] is None
    assert published[0][2]["services_requested"] == []


def test_realtime_notification_package_has_no_model_rag_or_agent_dependency() -> None:
    package = Path(__file__).parents[1] / "central_api" / "domains" / "realtime"
    forbidden: list[tuple[str, str]] = []
    for source_path in package.glob("*.py"):
        tree = ast.parse(source_path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if any(part in {"agents", "rag", "rfp"} for part in module.split(".")):
                    forbidden.append((source_path.name, module))
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(part in {"agents", "rag", "rfp"} for part in alias.name.split(".")):
                        forbidden.append((source_path.name, alias.name))
    assert forbidden == []
