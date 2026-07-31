"""Graph-level evals for the Engagement 8 LangGraph agent (Parts 1-2).

The routing model, retrieval, generation, and the ticket tool are mocked, so no live provider or DB
is needed. These assert automatic routing (RAG / ticket / both), answer GROUNDING in retrieved
context, honest tool fallbacks (never a fabricated status), and that every run yields a queryable,
ordered trace of node steps and tool calls carrying only safe metadata.
"""

from __future__ import annotations

import pytest

from central_api.domains.agents import graph as g
from central_api.domains.agents.config import AgentConfig
from central_api.domains.agents.routing import RouteDecision
from central_api.domains.agents.tools.incidents import TicketLookupResult, TicketStatus


class _RagCfg:
    min_score = 0.5
    openai_api_key = ""  # empty -> routing uses the deterministic heuristic (no live call)


def _config() -> AgentConfig:
    return AgentConfig(
        agent_name="trackflow-cx-agent", rag=_RagCfg(), min_score=0.5,
        agent_model="gpt-4o-mini", route_timeout_seconds=8.0, ticket_timeout_seconds=5.0,
    )


def _names(result: g.AgentRunResult) -> list[str]:
    return [step["node_name"] for step in result.steps]


def _route(monkeypatch: pytest.MonkeyPatch, decision: RouteDecision) -> None:
    monkeypatch.setattr(g, "route_question", lambda _q, _c: decision)


def _capturing_generate(store: dict[str, object], answer: str):
    """A generate_answer stub that records the context chunks and returns a fixed answer."""

    def generate(_question: str, chunks: list[dict[str, object]], _cfg: object) -> str:
        store["chunks"] = chunks
        return answer

    return generate


def _ok_ticket(monkeypatch: pytest.MonkeyPatch, ticket_id: int = 42) -> None:
    ticket = TicketStatus(ticket_id=ticket_id, status="resolved", category="lost_parcel",
                          created_at="2026-07-01T00:00:00+00:00", updated_at="2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(
        g, "lookup_ticket_status", lambda _id, timeout_seconds=5.0: TicketLookupResult("ok", ticket, 12)
    )


# --------------------------------------------------------------------------- RAG routing

def test_rag_route_flows_through_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [{"text": "30 days."}])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "Our return window is 30 days.")

    result = g.run_agent("what is the return window?", _config())

    assert result.status == "ok" and result.answer == "Our return window is 30 days."
    assert _names(result) == ["receive_question", "route", "retrieve", "generate"]
    assert result.route_taken == "rag" and not result.tool_calls


def test_answer_is_grounded_in_retrieved_context(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    chunk = {"source_document": "returns-policy", "section": "window", "text": "Return window: 30 days."}
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [chunk])
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "ok"))

    g.run_agent("return window?", _config())

    assert seen["chunks"] == [chunk]  # the RAG context reached generation


def test_no_context_routes_to_honest_node(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "I don't have that documented.")

    result = g.run_agent("do you take crypto?", _config())

    assert _names(result) == ["receive_question", "route", "retrieve", "no_context"]
    assert result.route_taken == "rag:no_context"


def test_retrieval_failure_returns_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None))

    def boom(_q: str, config: object = None) -> list[dict[str, object]]:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(g, "retrieve", boom)

    result = g.run_agent("anything", _config())

    assert result.status == "error" and result.answer is None
    assert _names(result) == ["receive_question", "route", "retrieve"]
    assert result.steps[-1]["status"] == "error"


def test_empty_question_is_rejected_before_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    result = g.run_agent("   ", _config())
    assert result.status == "rejected" and result.route_taken == "reject"
    assert _names(result) == ["receive_question"]


# --------------------------------------------------------------------------- tool routing

def test_ticket_route_calls_tool_and_grounds_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    _route(monkeypatch, RouteDecision("ticket", 42))
    _ok_ticket(monkeypatch)
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "Ticket 42 is resolved."))

    result = g.run_agent("what's the status of ticket 42?", _config())

    assert result.status == "ok" and result.answer == "Ticket 42 is resolved."
    assert _names(result) == ["receive_question", "route", "ticket_tool", "generate"]
    assert result.route_taken == "ticket"
    assert [call["tool_name"] for call in result.tool_calls] == ["ticket_status"]
    assert result.tool_calls[0]["status"] == "ok"
    # The live ticket fact was folded into the generation context.
    assert "status=resolved" in seen["chunks"][0]["text"]  # type: ignore[index]


def test_both_route_runs_rag_then_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("both", 7))
    _ok_ticket(monkeypatch, ticket_id=7)
    monkeypatch.setattr(g, "retrieve", lambda _q, config=None: [{"text": "Returns take 14 days."}])
    seen: dict[str, object] = {}
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "answer"))

    result = g.run_agent("status of ticket 7 and the returns policy?", _config())

    assert _names(result) == ["receive_question", "route", "retrieve", "ticket_tool", "generate"]
    assert result.route_taken == "both"
    texts = " ".join(chunk["text"] for chunk in seen["chunks"])  # type: ignore[index,union-attr]
    assert "Returns take 14 days." in texts and "Ticket 7" in texts


def test_tool_timeout_falls_back_without_fabricating(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("ticket", 99))
    monkeypatch.setattr(
        g, "lookup_ticket_status", lambda _id, timeout_seconds=5.0: TicketLookupResult("timeout", None, 5000)
    )
    seen: dict[str, object] = {}
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "I couldn't confirm that."))

    result = g.run_agent("status of ticket 99?", _config())

    assert result.status == "ok"
    assert result.tool_calls[0]["status"] == "timeout"
    fallback_text = seen["chunks"][0]["text"]  # type: ignore[index]
    assert "could not be confirmed" in fallback_text and "resolved" not in fallback_text


def test_routing_heuristic_extracts_ticket_id_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no OpenAI key, real route_question must still route a ticket question via the heuristic."""
    captured: dict[str, int] = {}

    def fake_lookup(ticket_id: int, timeout_seconds: float = 5.0) -> TicketLookupResult:
        captured["id"] = ticket_id
        return TicketLookupResult("not_found", None, 3)

    monkeypatch.setattr(g, "lookup_ticket_status", fake_lookup)
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "Ticket 7 was not found.")

    result = g.run_agent("can you check the status of ticket 7?", _config())

    assert captured["id"] == 7  # heuristic extracted the id and the tool was called
    assert result.route_taken == "ticket"


def test_trace_records_carry_only_safe_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("ticket", 42))
    _ok_ticket(monkeypatch)
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg: "answer")

    result = g.run_agent("status of ticket 42?", _config())

    step_keys = {
        "node_name", "sequence", "status", "started_at", "ended_at",
        "duration_ms", "tokens", "cost_usd", "notes",
    }
    for step in result.steps:
        assert set(step) == step_keys
    for call in result.tool_calls:
        assert set(call) == {"tool_name", "status", "duration_ms", "error_type"}
