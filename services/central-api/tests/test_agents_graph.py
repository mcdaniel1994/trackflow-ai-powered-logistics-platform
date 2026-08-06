"""Graph-level evals for the Engagement 8 LangGraph agent (Parts 1-2).

The routing model, retrieval, generation, and the ticket tool are mocked, so no live provider or DB
is needed. These assert automatic routing (RAG / ticket / both), answer GROUNDING in retrieved
context, honest tool fallbacks (never a fabricated status), and that every run yields a queryable,
ordered trace of node steps and tool calls carrying only safe metadata.
"""

from __future__ import annotations

import pytest
from pipelines.rag import GenerationResult

from central_api.domains.agents import graph as g
from central_api.domains.agents.config import AgentConfig
from central_api.domains.agents.mcp_client import TicketLookupResult, TicketStatus
from central_api.domains.agents.pricing import ModelUsage
from central_api.domains.agents.routing import RouteDecision


class _RagCfg:
    min_score = 0.5
    openai_api_key = ""  # empty -> routing uses the deterministic heuristic (no live call)
    generation_model = "deepseek-chat"  # unpriced alias -> generation tokens recorded, cost stays None


def _config() -> AgentConfig:
    return AgentConfig(
        agent_name="trackflow-cx-agent",
        rag=_RagCfg(),
        min_score=0.5,
        agent_model="gpt-4o-mini",
        route_timeout_seconds=8.0,
        ticket_timeout_seconds=5.0,
        mcp_url="http://mcp.test/mcp",
        mcp_resource_url="https://mcp.trackflow.test/mcp",
        oauth_token_url="http://identity.test/oauth/token",
        mcp_oauth_client_id="client",
        mcp_oauth_client_secret="secret",
        source_access_token="source-token",
    )


def _names(result: g.AgentRunResult) -> list[str]:
    return [step["node_name"] for step in result.steps]


def _route(monkeypatch: pytest.MonkeyPatch, decision: RouteDecision) -> None:
    monkeypatch.setattr(g, "route_question", lambda _q, _c: decision)


def _capturing_generate(store: dict[str, object], answer: str):
    """A generate_answer stub that records the context chunks and returns a fixed answer."""

    def generate(_question: str, chunks: list[dict[str, object]], _cfg: object, **_kwargs: object) -> str:
        store["chunks"] = chunks
        return answer

    return generate


def _ok_ticket(monkeypatch: pytest.MonkeyPatch, ticket_id: int = 42) -> None:
    ticket = TicketStatus(
        ticket_id=ticket_id,
        status="resolved",
        category="lost_parcel",
        created_at="2026-07-01T00:00:00+00:00",
        updated_at="2026-07-05T00:00:00+00:00",
    )
    monkeypatch.setattr(g, "lookup_ticket_status", lambda _id, _config: TicketLookupResult("ok", ticket, 12))


# --------------------------------------------------------------------------- RAG routing


def test_rag_route_flows_through_generate(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [{"text": "30 days."}])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg, **_k: "Our return window is 30 days.")

    result = g.run_agent("what is the return window?", _config(), "US")

    assert result.status == "ok" and result.answer == "Our return window is 30 days."
    assert _names(result) == [
        "receive_question",
        "guardrail_input",
        "route",
        "retrieve",
        "generate",
        "guardrail_output",
        "memory_selfeval",
    ]
    assert result.route_taken == "rag" and not result.tool_calls


def test_route_usage_is_attached_once_to_the_route_step(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None, ModelUsage(100, 20, 120, cost_usd=0.000027)))
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [{"text": "Documented."}])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg, **_k: "Answer.")

    result = g.run_agent("documented question?", _config(), "US")

    route_step = next(step for step in result.steps if step["node_name"] == "route")
    assert route_step["tokens"] == 120
    assert route_step["cost_usd"] == pytest.approx(0.000027)
    assert sum(step["tokens"] or 0 for step in result.steps) == 120


def test_answer_is_grounded_in_retrieved_context(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    chunk = {"source_document": "returns-policy", "section": "window", "text": "Return window: 30 days."}
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [chunk])
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "ok"))

    g.run_agent("return window?", _config(), "US")

    assert seen["chunks"] == [chunk]  # the RAG context reached generation


def test_current_rag_evidence_outranks_conflicting_memory(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    current = {
        "source_document": "carrier-coverage",
        "section": "UPS Ground",
        "text": "UPS Ground currently covers the continental US.",
        "subject_key": "coverage",
    }
    memory = {
        "source_document": "confirmed-memory",
        "carrier_name": "UPS Ground",
        "subject_key": "coverage",
        "text": "UPS Ground no longer covers the continental US.",
    }
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [current])
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "Current coverage applies."))

    result = g.run_agent("Does UPS Ground cover this region?", _config(), "US", [memory])

    assert seen["chunks"] == [current]
    assert any(event["rule_id"] == "memory_authority_omitted" for event in result.guardrail_events)


def test_candidate_from_single_generation_call_runs_selfeval_after_output_guardrail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = {
        "carrier_id": "11111111-1111-4111-8111-111111111111",
        "jurisdiction": "US",
        "kind": "recurring_operational_pattern",
        "subject_key": "late_scan_pattern",
        "fact": "Late scans recur during Tuesday handoffs.",
        "recurrence_count": 3,
        "effective_at": None,
    }
    calls = 0

    def generate(*_args: object, **_kwargs: object) -> GenerationResult:
        nonlocal calls
        calls += 1
        return GenerationResult("The current documented pattern applies.", candidate)

    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [{"text": "Documented pattern."}])
    monkeypatch.setattr(g, "generate_answer", generate)

    result = g.run_agent("What pattern applies?", _config(), "US")

    assert calls == 1
    assert result.memory_candidate == candidate
    assert _names(result)[-2:] == ["guardrail_output", "memory_selfeval"]


def test_no_context_routes_to_honest_node(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None))
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [])
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg, **_k: "I don't have that documented.")

    result = g.run_agent("do you take crypto?", _config(), "US")

    assert _names(result) == [
        "receive_question",
        "guardrail_input",
        "route",
        "retrieve",
        "no_context",
        "guardrail_output",
        "memory_selfeval",
    ]
    assert result.route_taken == "rag:no_context"


def test_retrieval_failure_returns_clean_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("rag", None))

    def boom(_q: str, config: object = None) -> list[dict[str, object]]:
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(g, "retrieve", boom)

    result = g.run_agent("anything", _config(), "US")

    assert result.status == "error" and result.answer is None
    assert _names(result) == ["receive_question", "guardrail_input", "route", "retrieve"]
    assert result.steps[-1]["status"] == "error"


def test_empty_question_is_rejected_before_routing(monkeypatch: pytest.MonkeyPatch) -> None:
    result = g.run_agent("   ", _config(), "US")
    assert result.status == "rejected" and result.route_taken == "reject"
    assert _names(result) == ["receive_question"]


# --------------------------------------------------------------------------- tool routing


def test_ticket_route_calls_tool_and_grounds_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}
    _route(monkeypatch, RouteDecision("ticket", 42))
    _ok_ticket(monkeypatch)
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "Ticket 42 is resolved."))

    result = g.run_agent("what's the status of ticket 42?", _config(), "US")

    assert result.status == "ok" and result.answer == "Ticket 42 is resolved."
    assert _names(result) == [
        "receive_question",
        "guardrail_input",
        "route",
        "ticket_tool",
        "generate",
        "guardrail_output",
        "memory_selfeval",
    ]
    assert result.route_taken == "ticket"
    assert [call["tool_name"] for call in result.tool_calls] == ["ticket_status"]
    assert result.tool_calls[0]["status"] == "ok"
    # The live ticket fact was folded into the generation context.
    assert "status=resolved" in seen["chunks"][0]["text"]  # type: ignore[index]


def test_both_route_runs_rag_then_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("both", 7))
    _ok_ticket(monkeypatch, ticket_id=7)
    monkeypatch.setattr(g, "retrieve", lambda _q, **_kwargs: [{"text": "Returns take 14 days."}])
    seen: dict[str, object] = {}
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "answer"))

    result = g.run_agent("status of ticket 7 and the returns policy?", _config(), "US")

    assert _names(result) == [
        "receive_question",
        "guardrail_input",
        "route",
        "retrieve",
        "ticket_tool",
        "generate",
        "guardrail_output",
        "memory_selfeval",
    ]
    assert result.route_taken == "both"
    texts = " ".join(chunk["text"] for chunk in seen["chunks"])  # type: ignore[index,union-attr]
    assert "Returns take 14 days." in texts and "Ticket 7" in texts


def test_tool_timeout_falls_back_without_fabricating(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("ticket", 99))
    monkeypatch.setattr(g, "lookup_ticket_status", lambda _id, _config: TicketLookupResult("timeout", None, 5000))
    seen: dict[str, object] = {}
    monkeypatch.setattr(g, "generate_answer", _capturing_generate(seen, "I couldn't confirm that."))

    result = g.run_agent("status of ticket 99?", _config(), "US")

    assert result.status == "ok"
    assert result.tool_calls[0]["status"] == "timeout"
    fallback_text = seen["chunks"][0]["text"]  # type: ignore[index]
    assert "could not be confirmed" in fallback_text and "resolved" not in fallback_text


def test_routing_heuristic_extracts_ticket_id_without_a_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no OpenAI key, real route_question must still route a ticket question via the heuristic."""
    captured: dict[str, int] = {}

    def fake_lookup(ticket_id: int, _config: AgentConfig) -> TicketLookupResult:
        captured["id"] = ticket_id
        return TicketLookupResult("not_found", None, 3)

    monkeypatch.setattr(g, "lookup_ticket_status", fake_lookup)
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg, **_k: "Ticket 7 was not found.")

    result = g.run_agent("can you check the status of ticket 7?", _config(), "US")

    assert captured["id"] == 7  # heuristic extracted the id and the tool was called
    assert result.route_taken == "ticket"


def test_trace_records_carry_only_safe_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    _route(monkeypatch, RouteDecision("ticket", 42))
    _ok_ticket(monkeypatch)
    monkeypatch.setattr(g, "generate_answer", lambda _q, _c, _cfg, **_k: "answer")

    result = g.run_agent("status of ticket 42?", _config(), "US")

    step_keys = {
        "node_name",
        "sequence",
        "status",
        "started_at",
        "ended_at",
        "duration_ms",
        "tokens",
        "cost_usd",
        "notes",
    }
    for step in result.steps:
        assert set(step) == step_keys
    for call in result.tool_calls:
        assert set(call) == {"tool_name", "status", "duration_ms", "error_type"}
