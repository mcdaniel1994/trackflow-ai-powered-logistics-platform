"""The Engagement 8 LangGraph agent — Phases 1-3 (RAG, routing, and OAuth-protected MCP tools).

Part 1 made the RAG flow an explicit, traceable state machine. Part 2 adds automatic routing and a
live tool: the agent decides on its own whether a question needs the knowledge base (RAG), a live
support-ticket lookup through the standalone MCP server, or both — without the user specifying —
and the trace shows which ran and in what order.

Nodes: ``receive_question`` -> ``route`` -> (conditional) ``retrieve`` / ``ticket_tool`` ->
``generate`` | ``no_context`` -> END. Retrieval and generation reuse the pipeline's ``retrieve`` and
``generate_answer`` (a tool result is folded in as an extra context block, so generation stays
reused, not duplicated). Every node records safe timing/status metadata; every tool call records a
typed ``tool_call``. The OpenAI routing model and the ticket tool have explicit timeouts and honest
fallbacks — a tool outage never fabricates a status. Guardrail and memory nodes arrive in Parts 4-5.
"""

from __future__ import annotations

import logging
import operator
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pipelines.rag import generate_answer, retrieve  # type: ignore[import-untyped]

from .config import AgentConfig
from .mcp_client import lookup_ticket_status
from .routing import route_question

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AgentState(TypedDict):
    """Minimal, explicit graph state — deliberately NOT the full conversation history."""

    question: str
    trace_id: str
    agent_name: str
    route: str
    ticket_id: int | None
    retrieved: list[dict[str, object]] | None
    tool_context: Annotated[list[dict[str, object]], operator.add]
    tool_calls: Annotated[list[dict[str, Any]], operator.add]
    answer: str | None
    error: str | None
    steps: Annotated[list[dict[str, Any]], operator.add]


@dataclass(frozen=True)
class AgentRunResult:
    """Everything needed to persist and return one run."""

    trace_id: str
    agent_name: str
    status: str  # ok | error | rejected
    route_taken: str
    answer: str | None
    started_at: datetime
    ended_at: datetime
    duration_ms: int
    steps: list[dict[str, Any]]
    tool_calls: list[dict[str, Any]]


def _step(state: AgentState, node_name: str, status: str, started: float, *, notes: str | None) -> dict[str, Any]:
    """Build one safe node-step record (metadata only)."""
    now = _utc_now()
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    return {
        "node_name": node_name,
        "sequence": len(state.get("steps", [])) + 1,
        "status": status,
        "started_at": now.isoformat(),
        "ended_at": now.isoformat(),
        "duration_ms": duration_ms,
        "tokens": None,
        "cost_usd": None,
        "notes": notes,
    }


def build_graph(config: AgentConfig) -> Any:
    """Compile the agent graph with routing, retrieval, and tools bound to ``config``.

    Config is bound via closures, never placed in graph state, so provider keys never enter the
    checkpointer. Compilation validates the graph structure and fails clearly on a bad topology.
    """

    def receive_question(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        if not state["question"].strip():
            return {"route": "reject", "error": "empty_question",
                    "steps": [_step(state, "receive_question", "error", started, notes="empty question")]}
        return {"steps": [_step(state, "receive_question", "ok", started, notes=None)]}

    def route_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        decision = route_question(state["question"], config)
        return {
            "route": decision.route,
            "ticket_id": decision.ticket_id,
            "steps": [_step(state, "route", "ok", started, notes=f"route={decision.route}")],
        }

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            chunks = retrieve(state["question"], config=config.rag)
        except Exception as exc:
            logger.warning("agent_retrieve_failed error_type=%s", type(exc).__name__)
            return {"retrieved": [], "error": "retrieval_failed",
                    "steps": [_step(state, "retrieve", "error", started, notes="retrieval failed")]}
        return {"retrieved": chunks,
                "steps": [_step(state, "retrieve", "ok", started, notes=f"chunks={len(chunks)}")]}

    def ticket_tool_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        ticket_id = state.get("ticket_id")
        if ticket_id is None:  # routing guarantees an id for tool routes; defensive only
            block = {"source_document": "ticket", "section": "status", "text": "No ticket id was provided."}
            call = {"tool_name": "ticket_status", "status": "error", "duration_ms": 0, "error_type": "missing_id"}
            return {"tool_context": [block], "tool_calls": [call],
                    "steps": [_step(state, "ticket_tool", "error", started, notes="missing ticket id")]}

        result = lookup_ticket_status(ticket_id, config)
        if result.outcome == "ok" and result.ticket is not None:
            ticket = result.ticket
            text = (
                f"Ticket {ticket.ticket_id}: status={ticket.status}, category={ticket.category}, "
                f"opened {ticket.created_at}, last updated {ticket.updated_at}."
            )
            call_status, step_status, notes = "ok", "ok", f"ticket={ticket_id} status={ticket.status}"
        elif result.outcome == "not_found":
            text = f"Ticket {ticket_id} was not found in the incident system."
            call_status, step_status, notes = "ok", "ok", f"ticket={ticket_id} not_found"
        else:  # timeout | error -> honest fallback, never a fabricated status
            text = (
                f"The current status of ticket {ticket_id} could not be confirmed right now. "
                "Tell the user you couldn't confirm it and to try again shortly."
            )
            call_status = "timeout" if result.outcome == "timeout" else "error"
            step_status, notes = "error", f"ticket={ticket_id} {result.outcome}"

        block = {"source_document": f"ticket-{ticket_id}", "section": "status", "text": text}
        call = {
            "tool_name": "ticket_status",
            "status": call_status,
            "duration_ms": result.duration_ms,
            "error_type": None if call_status == "ok" else result.outcome,
        }
        return {"tool_context": [block], "tool_calls": [call],
                "steps": [_step(state, "ticket_tool", step_status, started, notes=notes)]}

    def generate_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        context = list(state.get("retrieved") or []) + list(state.get("tool_context") or [])
        try:
            answer = generate_answer(state["question"], context, config.rag)
        except Exception as exc:
            logger.warning("agent_generate_failed error_type=%s", type(exc).__name__)
            return {"error": "generation_failed",
                    "steps": [_step(state, "generate", "error", started, notes="generation failed")]}
        return {"answer": answer,
                "steps": [_step(state, "generate", "ok", started, notes="grounded answer")]}

    def no_context_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            answer = generate_answer(state["question"], [], config.rag)
        except Exception as exc:
            logger.warning("agent_no_context_failed error_type=%s", type(exc).__name__)
            return {"error": "generation_failed",
                    "steps": [_step(state, "no_context", "error", started, notes="generation failed")]}
        return {"answer": answer,
                "steps": [_step(state, "no_context", "ok", started, notes="no grounded context")]}

    def after_receive(state: AgentState) -> str:
        return "reject" if state.get("route") == "reject" else "route"

    def after_route(state: AgentState) -> str:
        return "ticket_tool" if state["route"] == "ticket" else "retrieve"

    def after_retrieve(state: AgentState) -> str:
        if state.get("error"):
            return "end"
        if state["route"] == "both":
            return "ticket_tool"
        return "generate" if state.get("retrieved") else "no_context"

    graph = StateGraph(AgentState)
    graph.add_node("receive_question", receive_question)
    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("ticket_tool", ticket_tool_node)
    graph.add_node("generate", generate_node)
    graph.add_node("no_context", no_context_node)

    graph.add_edge(START, "receive_question")
    graph.add_conditional_edges("receive_question", after_receive, {"reject": END, "route": "route"})
    graph.add_conditional_edges("route", after_route, {"retrieve": "retrieve", "ticket_tool": "ticket_tool"})
    graph.add_conditional_edges(
        "retrieve", after_retrieve,
        {"ticket_tool": "ticket_tool", "generate": "generate", "no_context": "no_context", "end": END},
    )
    graph.add_edge("ticket_tool", "generate")
    graph.add_edge("generate", END)
    graph.add_edge("no_context", END)

    return graph.compile(checkpointer=MemorySaver())


def _route_taken(state: AgentState, reject: bool) -> str:
    if reject:
        return "reject"
    names = {step["node_name"] for step in state.get("steps", [])}
    ran_tool = "ticket_tool" in names
    ran_rag = "retrieve" in names
    if ran_tool and ran_rag:
        return "both"
    if ran_tool:
        return "ticket"
    if "no_context" in names:
        return "rag:no_context"
    return "rag"


def run_agent(question: str, config: AgentConfig) -> AgentRunResult:
    """Invoke the compiled graph once and return a structured, persistable run result."""
    graph = build_graph(config)
    trace_id = uuid4().hex
    started_at = _utc_now()
    perf_start = time.perf_counter()

    initial: AgentState = {
        "question": question,
        "trace_id": trace_id,
        "agent_name": config.agent_name,
        "route": "",
        "ticket_id": None,
        "retrieved": None,
        "tool_context": [],
        "tool_calls": [],
        "answer": None,
        "error": None,
        "steps": [],
    }
    final: AgentState = graph.invoke(initial, config={"configurable": {"thread_id": trace_id}})

    ended_at = _utc_now()
    duration_ms = max(0, int((time.perf_counter() - perf_start) * 1000))
    reject = final.get("route") == "reject"
    if reject:
        status = "rejected"
    elif final.get("error"):
        status = "error"
    else:
        status = "ok"

    return AgentRunResult(
        trace_id=trace_id,
        agent_name=config.agent_name,
        status=status,
        route_taken=_route_taken(final, reject),
        answer=final.get("answer"),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        steps=final.get("steps", []),
        tool_calls=final.get("tool_calls", []),
    )
