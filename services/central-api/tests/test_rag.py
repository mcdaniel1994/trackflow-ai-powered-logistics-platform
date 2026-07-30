"""Endpoint tests for POST /knowledge/query (Engagement 7).

The pipeline's ``query`` is mocked, so no live Qdrant or LLM provider is needed. These cover
auth, validation, the disabled-vs-configured branches, and pipeline-failure translation.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from central_api.core.config import Settings, get_settings
from central_api.domains.rag import service as rag_service


def _configure_rag(app: FastAPI, base: Settings) -> None:
    """Point the app at a fully-configured RAG settings object."""
    configured = Settings(
        database_url=base.database_url,
        identity_jwt_public_key=base.identity_jwt_public_key,
        rag_enabled=True,
        openai_api_key="test-openai",
        deepseek_api_key="test-deepseek",
    )
    app.dependency_overrides[get_settings] = lambda: configured


def test_query_returns_generated_answer(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_rag(app, settings)
    seen: dict[str, str] = {}

    def fake_query(question: str, _config: object) -> str:
        seen["question"] = question
        return "Our standard return window is 30 days from delivery."

    monkeypatch.setattr(rag_service, "query", fake_query)

    response = client.post("/knowledge/query", json={"question": "return window?"}, headers=auth_headers)

    assert response.status_code == 200
    assert response.json() == {"answer": "Our standard return window is 30 days from delivery."}
    assert seen["question"] == "return window?"  # trimmed question reached the pipeline


def test_query_requires_authentication(client: TestClient) -> None:
    response = client.post("/knowledge/query", json={"question": "anything"})
    assert response.status_code == 401


def test_query_rejects_blank_question(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
) -> None:
    _configure_rag(app, settings)
    response = client.post("/knowledge/query", json={"question": "   "}, headers=auth_headers)
    assert response.status_code == 422


def test_query_unavailable_when_not_configured(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    # Default test settings leave RAG disabled.
    response = client.post("/knowledge/query", json={"question": "anything"}, headers=auth_headers)
    assert response.status_code == 503


def test_query_translates_pipeline_failure(
    app: FastAPI,
    client: TestClient,
    settings: Settings,
    auth_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _configure_rag(app, settings)

    def boom(_question: str, _config: object) -> str:
        raise rag_service.RagPipelineError("provider down")

    monkeypatch.setattr(rag_service, "query", boom)

    response = client.post("/knowledge/query", json={"question": "anything"}, headers=auth_headers)

    assert response.status_code == 502
    # No provider or vector-store internals leak to the client.
    assert "provider down" not in response.text
