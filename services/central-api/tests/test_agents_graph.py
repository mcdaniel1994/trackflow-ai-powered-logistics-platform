"""Graph-level evals for the Engagement 8 LangGraph agent (Phase 1).

The pipeline's ``retrieve``/``generate_answer`` are mocked, so no live Qdrant or LLM provider is
needed. These assert the conditional routing (RAG hit -> generate; no context -> honest node;
retrieval failure -> clean error; empty -> reject), answer GROUNDING in the retrieved context, and
that each run yields a queryable, ordered trace.
"""

from __future__ import annotations

import pytest

from central_api.domains.agents import graph as g
from central_api.domains.agents.config import AgentConfig


class _RagCfg:
    min_score = 0.5


def _config() -> AgentConfig:
    return AgentConfig(agent_name="trackflow-cx-agent", rag=_RagCfg(), min_score=0.5)


def test_rag_hit_routes_through_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [{"text": "30 days."}])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "Our return window is 30 days.")

    result = g.run_agent("what is the return window?", _config())

    assert result.status == "ok"
    assert result.answer == "Our return window is 30 days."
    assert [step["node_name"] for step in result.steps] == ["receive_question", "retrieve", "generate"]
    assert result.route_taken == "rag"
    assert len(result.trace_id) == 32
    assert all(step["sequence"] == i + 1 for i, step in enumerate(result.steps))


def test_answer_is_grounded_in_retrieved_context(monkeypatch: pytest.MonkeyPatch) -> None:
    """A grounding eval: the retrieved chunks must reach generation (not be ignored)."""
    seen: dict[str, object] = {}
    chunk = {"source_document": "returns-policy", "section": "window", "text": "Return window: 30 days."}
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [chunk])

    def fake_generate(_question: str, chunks: list[dict[str, object]], _cfg: object) -> str:
        seen["chunks"] = chunks
        return "grounded answer"

    monkeypatch.setattr(g, "generate_answer", fake_generate)

    g.run_agent("return window?", _config())

    assert seen["chunks"] == [chunk]  # the RAG context was passed into generation


def test_no_context_routes_to_honest_node(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "I don't have that documented.")

    result = g.run_agent("do you take crypto?", _config())

    assert result.status == "ok"
    assert [step["node_name"] for step in result.steps] == ["receive_question", "retrieve", "no_context"]
    assert result.route_taken == "rag:no_context"


def test_retrieval_failure_returns_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_q: str, config: object = None) -> list[dict[str, object]]:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(g, "retrieve", boom)

    result = g.run_agent("anything", _config())

    assert result.status == "error"
    assert result.answer is None
    assert [step["node_name"] for step in result.steps] == ["receive_question", "retrieve"]
    assert result.steps[-1]["status"] == "error"


def test_empty_question_is_rejected_before_retrieval(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [])

    result = g.run_agent("   ", _config())

    assert result.status == "rejected"
    assert result.route_taken == "reject"
    assert [step["node_name"] for step in result.steps] == ["receive_question"]


def test_trace_steps_carry_only_safe_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    """No raw prompt/answer/retrieved text may appear in a node-step record."""
    secret_chunk = {"text": "SECRET warehouse route via Zaragoza depot 7"}
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [secret_chunk])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "SECRET answer body")

    result = g.run_agent("where is the depot?", _config())

    allowed_keys = {
        "node_name", "sequence", "status", "started_at", "ended_at",
        "duration_ms", "tokens", "cost_usd", "notes",
    }
    for step in result.steps:
        assert set(step) == allowed_keys
        assert "SECRET" not in (step["notes"] or "")
