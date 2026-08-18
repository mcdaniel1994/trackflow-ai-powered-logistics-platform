"""Phase 4 owner-scoped chat history API and HTTP-agent bridge."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from central_api.core.config import Settings, get_settings
from central_api.domains.agents import service as agent_service
from central_api.domains.agents.graph import AgentRunResult
from central_api.domains.chat.models import ChatMessage
from central_api.domains.chat.repository import ChatRepository

OWNER = "11111111-1111-4111-8111-111111111111"
OTHER_OWNER = "22222222-2222-4222-8222-222222222222"


def _enable_chat(app: FastAPI, base: Settings, *, runnable: bool = False) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        agents_enabled=True,
        rag_enabled=runnable,
        openai_api_key="test-openai" if runnable else "",
        deepseek_api_key="test-deepseek" if runnable else "",
        agent_mcp_oauth_client_id="test-client" if runnable else "",
        agent_mcp_oauth_client_secret="test-secret" if runnable else "",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def _result() -> AgentRunResult:
    now = datetime.now(UTC)
    return AgentRunResult(
        trace_id="chat-trace",
        agent_name="first_line_cx",
        status="ok",
        route_taken="rag",
        answer="The return window is 30 days.",
        started_at=now,
        ended_at=now,
        duration_ms=1,
        steps=[],
        tool_calls=[],
        guardrail_events=[],
    )


def test_chat_history_is_flag_gated(client: TestClient, auth_headers: dict[str, str]) -> None:
    assert client.get("/chat/sessions", headers=auth_headers).status_code == 503
    assert client.post("/chat/sessions", headers=auth_headers).status_code == 503


def test_chat_history_requires_auth_and_cookie_writes_require_csrf(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    cookie_auth: Any,
) -> None:
    _enable_chat(app, settings)
    assert client.get("/chat/sessions").status_code == 401
    cookie_auth(csrf=False)
    assert client.post("/chat/sessions").status_code == 403


def test_create_list_and_detail_are_owner_scoped(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
    token_factory: Any,
    engine: Engine,
) -> None:
    _enable_chat(app, settings)
    created = client.post("/chat/sessions", headers=auth_headers)
    assert created.status_code == 201
    session_id = created.json()["session_id"]
    assert created.json()["agent_id"] == "first_line_cx"
    assert created.json()["user_id"] == created.json()["client_id"] == OWNER

    with Session(engine) as database:
        repository = ChatRepository(database)
        repository.append_message_for_user(
            session_id=session_id,
            user_id=OWNER,
            role="user",
            content="Where is ticket 1?",
        )
        database.commit()

    listed = client.get("/chat/sessions", headers=auth_headers)
    assert [row["session_id"] for row in listed.json()] == [session_id]
    detail = client.get(f"/chat/sessions/{session_id}", headers=auth_headers)
    assert [message["content"] for message in detail.json()["messages"]] == ["Where is ticket 1?"]

    other_headers = {"Authorization": f"Bearer {token_factory(user_id=OTHER_OWNER)}"}
    assert client.get("/chat/sessions", headers=other_headers).json() == []
    assert client.get(f"/chat/sessions/{session_id}", headers=other_headers).status_code == 404


def test_chat_query_threads_session_persists_messages_and_never_traces_content(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
    engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configured = _enable_chat(app, settings, runnable=True)
    session_id = client.post("/chat/sessions", headers=auth_headers).json()["session_id"]
    calls: dict[str, object] = {}

    def run(*args: object, **kwargs: object) -> AgentRunResult:
        calls["run_args"] = args
        calls["run_kwargs"] = kwargs
        return _result()

    def persist(*_args: object, **kwargs: object) -> None:
        calls["persist_kwargs"] = kwargs

    monkeypatch.setattr(agent_service, "run_agent", run)
    monkeypatch.setattr(agent_service, "persist_run", persist)

    response = client.post(
        "/agent/query",
        json={
            "question": "What is the return window?",
            "conversation_id": session_id,
            "route": "knowledge",
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["conversation_id"] == session_id
    assert response.json()["route_taken"] == "rag"
    assert calls["run_kwargs"] == {"route_preference": "knowledge"}
    assert calls["persist_kwargs"] == {
        "env": configured.app_env,
        "input_summary": None,
        "output_summary": None,
    }

    with Session(engine) as database:
        messages = database.exec(select(ChatMessage).order_by(ChatMessage.sequence)).all()
        assert [(message.role, message.content) for message in messages] == [
            ("user", "What is the return window?"),
            ("assistant", "The return window is 30 days."),
        ]
