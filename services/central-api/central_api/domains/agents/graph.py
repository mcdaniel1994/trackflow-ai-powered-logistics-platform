"""The Engagement 8 LangGraph agent — Phase 1 (RAG migration).

The Engagement 7 RAG endpoint ran ``retrieve -> generate`` inside one opaque ``query()``. Here that
flow becomes an explicit, traceable state machine: single-responsibility nodes, conditional edges
with real conditions, a checkpointer, and a queryable trace of every node executed.

Phase 1 nodes: ``receive_question`` -> (conditional) ``retrieve`` -> (conditional)
``generate`` | ``no_context`` -> END. Retrieval and generation reuse the pipeline's
``retrieve`` and ``generate_answer`` (no logic duplicated). The OpenAI routing model and tool nodes
arrive in Part 2; guardrail and memory nodes in Parts 4-5. Each node records safe timing/status
metadata (no prompts, completions, retrieved text, or secrets) into ``state["steps"]``.
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

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AgentState(TypedDict):
    """Minimal, explicit graph state — deliberately NOT the full conversation history."""

    question: str
    trace_id: str
    agent_name: str
    retrieved: list[dict[str, object]] | None
    answer: str | None
    route: str
    error: str | None
    # Reducer: each node returns {"steps": [record]} and langgraph appends them in path order.
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


def _step(state: AgentState, node_name: str, status: str, started: float, *, notes: str | None) -> dict[str, Any]:
    """Build one safe node-step record (metadata only)."""
    now = _utc_now()
    duration_ms = max(0, int((time.perf_counter() - started) * 1000))
    return {
        "node_name": node_name,
        "sequence": len(state.get("steps", [])) + 1,
        "status": status,
        "started_at": (now).isoformat(),
        "ended_at": now.isoformat(),
        "duration_ms": duration_ms,
        "tokens": None,
        "cost_usd": None,
        "notes": notes,
    }


def build_graph(config: AgentConfig) -> Any:
    """Compile the agent graph with retrieval/generation bound to ``config``.

    Config is bound via closures, never placed in graph state, so provider keys never enter the
    checkpointer. Compilation validates the graph structure and fails clearly on a bad topology.
    """

    def receive_question(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        question = state["question"].strip()
        if not question:
            return {"route": "reject", "error": "empty_question",
                    "steps": [_step(state, "receive_question", "error", started, notes="empty question")]}
        return {"route": "rag", "steps": [_step(state, "receive_question", "ok", started, notes=None)]}

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            chunks = retrieve(state["question"], config=config.rag)
        except Exception as exc:  # provider/vector-store failure: clean error, no stack trace out
            logger.warning("agent_retrieve_failed error_type=%s", type(exc).__name__)
            return {"retrieved": [], "error": "retrieval_failed",
                    "steps": [_step(state, "retrieve", "error", started, notes="retrieval failed")]}
        return {"retrieved": chunks,
                "steps": [_step(state, "retrieve", "ok", started, notes=f"chunks={len(chunks)}")]}

    def generate_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            answer = generate_answer(state["question"], state["retrieved"] or [], config.rag)
        except Exception as exc:
            logger.warning("agent_generate_failed error_type=%s", type(exc).__name__)
            return {"error": "generation_failed",
                    "steps": [_step(state, "generate", "error", started, notes="generation failed")]}
        return {"answer": answer,
                "steps": [_step(state, "generate", "ok", started, notes="grounded answer")]}

    def no_context_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        try:
            # Reuse generation with an empty context -> the pipeline's honest "not documented" prompt.
            answer = generate_answer(state["question"], [], config.rag)
        except Exception as exc:
            logger.warning("agent_no_context_failed error_type=%s", type(exc).__name__)
            return {"error": "generation_failed",
                    "steps": [_step(state, "no_context", "error", started, notes="generation failed")]}
        return {"answer": answer, "route": "rag:no_context",
                "steps": [_step(state, "no_context", "ok", started, notes="no grounded context")]}

    def after_receive(state: AgentState) -> str:
        return "reject" if state["route"] == "reject" else "retrieve"

    def after_retrieve(state: AgentState) -> str:
        if state.get("error"):
            return "end"
        return "generate" if state.get("retrieved") else "no_context"

    graph = StateGraph(AgentState)
    graph.add_node("receive_question", receive_question)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("generate", generate_node)
    graph.add_node("no_context", no_context_node)

    graph.add_edge(START, "receive_question")
    graph.add_conditional_edges("receive_question", after_receive, {"reject": END, "retrieve": "retrieve"})
    graph.add_conditional_edges(
        "retrieve", after_retrieve, {"generate": "generate", "no_context": "no_context", "end": END}
    )
    graph.add_edge("generate", END)
    graph.add_edge("no_context", END)

    return graph.compile(checkpointer=MemorySaver())


def _route_taken(steps: list[dict[str, Any]], reject: bool) -> str:
    if reject:
        return "reject"
    names = {step["node_name"] for step in steps}
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
        "retrieved": None,
        "answer": None,
        "route": "",
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
        route_taken=_route_taken(final.get("steps", []), reject),
        answer=final.get("answer"),
        started_at=started_at,
        ended_at=ended_at,
        duration_ms=duration_ms,
        steps=final.get("steps", []),
    )
