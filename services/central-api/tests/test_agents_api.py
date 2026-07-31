"""Endpoint + trace-store tests for the Engagement 8 agent (Phase 1).

``run_agent`` is mocked for the endpoint tests, so no live provider is needed. They cover auth,
validation, the disabled-vs-configured branches, failure translation, the trace read endpoints, and
that no raw prompt/answer content is persisted unless content capture is explicitly enabled.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlmodel import Session

from central_api.core.config import Settings, get_settings
from central_api.domains.agents import recorder
from central_api.domains.agents import service as agent_service
from central_api.domains.agents.graph import AgentRunResult
from central_api.domains.agents.repository import AgentRepository


def _configure_agent(app: FastAPI, base: Settings, *, store_content: bool = False) -> Settings:
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        agents_enabled=True,
        agents_store_content=store_content,
        rag_enabled=True,
        openai_api_key="test-openai",
        deepseek_api_key="test-deepseek",
    )
    app.dependency_overrides[get_settings] = lambda: configured
    return configured


def _result(
    *, status: str = "ok", answer: str | None = "30 days.", trace_id: str = "trace-abc",
    with_tool: bool = False,
) -> AgentRunResult:
    now = datetime.now(UTC)
    steps = [
        {"node_name": "receive_question", "sequence": 1, "status": "ok", "started_at": now.isoformat(),
         "ended_at": now.isoformat(), "duration_ms": 1, "tokens": None, "cost_usd": None, "notes": None},
        {"node_name": "retrieve", "sequence": 2, "status": "ok", "started_at": now.isoformat(),
         "ended_at": now.isoformat(), "duration_ms": 4, "tokens": None, "cost_usd": None, "notes": "chunks=1"},
    ]
    tool_calls = (
        [{"tool_name": "ticket_status", "status": "ok", "duration_ms": 12, "error_type": None}]
        if with_tool else []
    )
    return AgentRunResult(
        trace_id=trace_id, agent_name="trackflow-cx-agent", status=status, route_taken="rag",
        answer=answer, started_at=now, ended_at=now, duration_ms=5, steps=steps, tool_calls=tool_calls,
    )


# --------------------------------------------------------------------------- endpoint

def test_query_returns_answer_and_trace_id(
    app: FastAPI, client: TestClient, settings: Settings, auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_agent(app, settings)
    monkeypatch.setattr(agent_service, "run_agent", lambda _q, _c: _result())
    monkeypatch.setattr(agent_service, "persist_run", lambda *a, **k: None)

    response = client.post("/agent/query", json={"question": "return window?"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"answer": "30 days.", "trace_id": "trace-abc"}


def test_query_requires_authentication(client: TestClient) -> None:
    assert client.post("/agent/query", json={"question": "anything"}).status_code == 401


def test_query_rejects_blank_question(
    app: FastAPI, client: TestClient, settings: Settings, auth_headers: dict[str, str],
) -> None:
    _configure_agent(app, settings)
    assert client.post("/agent/query", json={"question": "   "}, headers=auth_headers).status_code == 422


def test_query_unavailable_when_disabled(client: TestClient, auth_headers: dict[str, str]) -> None:
    # Default test settings leave the agent disabled.
    assert client.post("/agent/query", json={"question": "x"}, headers=auth_headers).status_code == 503


def test_query_translates_run_failure(
    app: FastAPI, client: TestClient, settings: Settings, auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_agent(app, settings)
    monkeypatch.setattr(agent_service, "run_agent", lambda _q, _c: _result(status="error", answer=None))
    monkeypatch.setattr(agent_service, "persist_run", lambda *a, **k: None)

    response = client.post("/agent/query", json={"question": "x"}, headers=auth_headers)

    assert response.status_code == 502
    assert "traceback" not in response.text.lower()


# --------------------------------------------------------------------------- trace read endpoints

def test_list_and_get_run_endpoints(
    app: FastAPI, client: TestClient, settings: Settings, engine: Engine, auth_headers: dict[str, str],
) -> None:
    _configure_agent(app, settings)
    # Insert a run directly through the recorder (its own session), then read via the API.
    recorder.persist_run(_result(trace_id="trace-xyz"), env="test", input_summary=None, output_summary=None)

    listing = client.get("/agents/runs", headers=auth_headers)
    assert listing.status_code == 200
    trace_ids = [row["trace_id"] for row in listing.json()]
    assert "trace-xyz" in trace_ids

    detail = client.get("/agents/runs/trace-xyz", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["trace_id"] == "trace-xyz"
    assert [step["node_name"] for step in body["node_steps"]] == ["receive_question", "retrieve"]
    assert body["input_summary"] is None  # no content persisted by default


def test_get_missing_run_is_404(
    app: FastAPI, client: TestClient, settings: Settings, auth_headers: dict[str, str],
) -> None:
    _configure_agent(app, settings)
    assert client.get("/agents/runs/does-not-exist", headers=auth_headers).status_code == 404


# --------------------------------------------------------------------------- trace store persistence

def test_persist_run_stores_metadata_without_content(engine: Engine) -> None:
    recorder.persist_run(
        _result(trace_id="trace-persist", with_tool=True), env="test", input_summary=None, output_summary=None
    )

    with Session(engine) as session:
        repo = AgentRepository(session)
        run = repo.get_run("trace-persist")
        assert run is not None and run.id is not None
        assert run.status == "ok" and run.route_taken == "rag"
        assert run.input_summary is None and run.output_summary is None  # content-free by default
        steps = repo.steps_for(run.id)
        assert [step.node_name for step in steps] == ["receive_question", "retrieve"]
        calls = repo.tool_calls_for(run.id)
        assert [call.tool_name for call in calls] == ["ticket_status"]
        assert calls[0].status == "ok" and calls[0].input_summary is None  # tool args not persisted


def test_content_capture_is_opt_in(engine: Engine) -> None:
    recorder.persist_run(
        _result(trace_id="trace-content"),
        env="test",
        input_summary="return window?",
        output_summary="30 days.",
    )
    with Session(engine) as session:
        run = AgentRepository(session).get_run("trace-content")
        assert run is not None
        assert run.input_summary == "return window?"  # stored only because summaries were provided
