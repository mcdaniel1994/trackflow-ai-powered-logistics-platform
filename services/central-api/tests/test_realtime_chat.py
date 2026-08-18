"""WebSocket chat auth, event contract, abort, redirect, and reconnect proofs."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from threading import Event
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pipelines.rag import GenerationCancelled  # type: ignore[import-untyped]
from starlette.websockets import WebSocketDisconnect

from central_api.core.config import Settings, get_settings
from central_api.domains.agents.graph import AgentRunResult
from central_api.domains.chat import streaming

ORIGIN = "https://backoffice.forgehub.cloud"
OWNER = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER = "22222222-2222-4222-8222-222222222222"


def _enable_chat(app: FastAPI, base: Settings) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        central_api_cors_origins=ORIGIN,
        agents_enabled=True,
        rag_enabled=True,
        openai_api_key="test-openai",
        deepseek_api_key="test-deepseek",
        agent_mcp_oauth_client_id="test-client",
        agent_mcp_oauth_client_secret="test-secret",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def _result(answer: str, *, route: str = "rag") -> AgentRunResult:
    now = datetime.now(UTC)
    return AgentRunResult(
        trace_id=f"trace-{answer}",
        agent_name="first_line_cx",
        status="ok",
        route_taken=route,
        answer=answer,
        started_at=now,
        ended_at=now,
        duration_ms=1,
        steps=[],
        tool_calls=[],
        guardrail_events=[],
    )


def _create_session(client: TestClient, cookie_auth: Any) -> str:
    csrf = cookie_auth()
    response = client.post("/chat/sessions", headers=csrf)
    assert response.status_code == 201
    return str(response.json()["session_id"])


def _event(socket: Any, expected: str) -> dict[str, Any]:
    while True:
        frame = socket.receive_json()
        if frame["event"] == expected:
            return frame


def test_websocket_rejects_bearer_only_and_cross_owner_before_accept(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    cookie_auth: Any,
    token_factory: Any,
) -> None:
    _enable_chat(app, settings)
    session_id = _create_session(client, cookie_auth)
    client.cookies.clear()

    with (
        pytest.raises(WebSocketDisconnect) as missing_cookie,
        client.websocket_connect(
            f"/realtime/chat/{session_id}",
            headers={"origin": ORIGIN, "Authorization": f"Bearer {token_factory()}"},
        ),
    ):
        pass
    assert missing_cookie.value.code == 1008

    client.cookies.set("trackflow_access", token_factory(user_id=OTHER_OWNER))
    with (
        pytest.raises(WebSocketDisconnect) as cross_owner,
        client.websocket_connect(f"/realtime/chat/{session_id}", headers={"origin": ORIGIN}),
    ):
        pass
    assert cross_owner.value.code == 1008


def test_websocket_streams_named_events_and_reconnects_with_snapshot(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    cookie_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_chat(app, settings)
    session_id = _create_session(client, cookie_auth)

    def run(*_args: object, **kwargs: object) -> AgentRunResult:
        callback = kwargs["token_callback"]
        callback("Your")
        callback(" parcel")
        return _result("Your parcel")

    monkeypatch.setattr(streaming, "run_agent", run)
    monkeypatch.setattr(streaming, "persist_run", lambda *_a, **_k: None)

    with client.websocket_connect(f"/realtime/chat/{session_id}", headers={"origin": ORIGIN}) as socket:
        snapshot = socket.receive_json()
        assert snapshot == {
            "event": "session_snapshot",
            "data": {
                "session_id": session_id,
                "status": "active",
                "messages": [],
                "active_generation": None,
            },
        }
        socket.send_json(
            {
                "event": "user_message",
                "data": {"session_id": session_id, "text": "Where is my parcel?", "route": "auto"},
            }
        )
        user = _event(socket, "user_message")
        first = _event(socket, "token_chunk")
        second = _event(socket, "token_chunk")
        completed = _event(socket, "generation_completed")
        assert user["data"]["message"]["content"] == "Where is my parcel?"
        assert [first["data"]["token"], second["data"]["token"]] == ["Your", " parcel"]
        assert first["data"]["sequence"] == 1 and second["data"]["sequence"] == 2
        assert completed["data"]["message_id"]

    with client.websocket_connect(f"/realtime/chat/{session_id}", headers={"origin": ORIGIN}) as reconnected:
        snapshot = reconnected.receive_json()
        assert snapshot["event"] == "session_snapshot"
        assert [(message["role"], message["content"]) for message in snapshot["data"]["messages"]] == [
            ("user", "Where is my parcel?"),
            ("assistant", "Your parcel"),
        ]


def test_interrupt_stops_tokens_keeps_partial_and_starts_redirected_turn(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    cookie_auth: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_chat(app, settings)
    session_id = _create_session(client, cookie_auth)
    calls = 0
    provider_closed = Event()

    def run(*_args: object, **kwargs: object) -> AgentRunResult:
        nonlocal calls
        calls += 1
        callback = kwargs["token_callback"]
        cancelled = kwargs["cancelled"]
        if calls == 1:
            kwargs["stream_started"](provider_closed.set)
            callback("Tracking")
            while not cancelled() and not provider_closed.is_set():
                time.sleep(0.001)
            raise GenerationCancelled("cancelled")
        callback("Return started")
        return _result("Return started")

    monkeypatch.setattr(streaming, "run_agent", run)
    monkeypatch.setattr(streaming, "persist_run", lambda *_a, **_k: None)

    with client.websocket_connect(f"/realtime/chat/{session_id}", headers={"origin": ORIGIN}) as socket:
        assert socket.receive_json()["event"] == "session_snapshot"
        socket.send_json(
            {
                "event": "user_message",
                "data": {"session_id": session_id, "text": "Track parcel 1", "route": "auto"},
            }
        )
        _event(socket, "user_message")
        token = _event(socket, "token_chunk")
        assert token["data"]["token"] == "Tracking"
        with client.websocket_connect(
            f"/realtime/chat/{session_id}", headers={"origin": ORIGIN}
        ) as reconnected_during_generation:
            live_snapshot = reconnected_during_generation.receive_json()
            assert live_snapshot["data"]["active_generation"] == {
                "generation_id": token["data"]["generation_id"],
                "content": "Tracking",
                "sequence": 1,
            }
        socket.send_json(
            {
                "event": "interrupt_requested",
                "data": {
                    "session_id": session_id,
                    "new_input": "Start a return instead",
                    "route": "knowledge",
                },
            }
        )
        interrupted = _event(socket, "generation_interrupted")
        redirected_user = _event(socket, "user_message")
        redirected_token = _event(socket, "token_chunk")
        completed = _event(socket, "generation_completed")
        assert interrupted["data"]["status"] == "interrupted"
        assert interrupted["data"]["message_id"]
        assert redirected_user["data"]["message"]["content"] == "Start a return instead"
        assert redirected_token["data"]["token"] == "Return started"
        assert completed["data"]["message_id"]
        assert calls == 2
        assert provider_closed.is_set()

    with client.websocket_connect(f"/realtime/chat/{session_id}", headers={"origin": ORIGIN}) as reconnected:
        messages = reconnected.receive_json()["data"]["messages"]
        assert [(message["content"], message["interrupted"]) for message in messages] == [
            ("Track parcel 1", False),
            ("Tracking", True),
            ("Start a return instead", False),
            ("Return started", False),
        ]
