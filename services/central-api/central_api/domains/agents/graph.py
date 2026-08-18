"""The Engagement 8 LangGraph agent — Phases 1-5.

Part 1 made the RAG flow an explicit, traceable state machine. Part 2 adds automatic routing and a
live tool: the agent decides on its own whether a question needs the knowledge base (RAG), a live
support-ticket lookup through the standalone MCP server, or both — without the user specifying —
and the trace shows which ran and in what order. Phase 4 wraps routing/evidence/generation with
deterministic jurisdiction, injection, tool-argument, and output controls.

Nodes: ``receive_question`` -> ``guardrail_input`` -> ``route`` -> (conditional) ``retrieve`` /
``ticket_tool`` -> ``generate`` | ``no_context`` -> ``guardrail_output`` -> END. Retrieval and
generation reuse the pipeline's ``retrieve`` and
``generate_answer`` (a tool result is folded in as an extra context block, so generation stays
reused, not duplicated). Every node records safe timing/status metadata; every tool call records a
typed ``tool_call``. The OpenAI routing model and the ticket tool have explicit timeouts and honest
fallbacks — a tool outage never fabricates a status. Phase 5 adds lower-authority, human-confirmed
structured memory and a post-guardrail candidate self-evaluation node.
"""

from __future__ import annotations

import logging
import operator
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, Any, Literal, TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from pipelines.rag import (  # type: ignore[import-untyped]
    GenerationCancelled,
    GenerationResult,
    generate_answer,
    retrieve,
)

from .config import AgentConfig
from .guardrails import (
    JURISDICTION_REQUIRED,
    OUTPUT_FALLBACK,
    evidence_is_safe,
    validate_input,
    validate_output,
    validate_ticket_argument,
)
from .mcp_client import lookup_ticket_status
from .pricing import usage_from_counters
from .routing import route_question

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(UTC)


class AgentState(TypedDict):
    """Minimal, explicit graph state — deliberately NOT the full conversation history."""

    question: str
    trace_id: str
    agent_name: str
    jurisdiction: str | None
    route_preference: Literal["auto", "knowledge", "ticket"]
    route: str
    ticket_id: int | None
    retrieved: list[dict[str, object]] | None
    memory_evidence: list[dict[str, object]]
    memory_candidate: dict[str, object] | None
    tool_context: Annotated[list[dict[str, object]], operator.add]
    tool_calls: Annotated[list[dict[str, Any]], operator.add]
    answer: str | None
    authoritative_status: str | None
    guardrail_events: Annotated[list[dict[str, Any]], operator.add]
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
    guardrail_events: list[dict[str, Any]] = field(default_factory=list)
    memory_candidate: dict[str, object] | None = None


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


def _record_generation_usage(step: dict[str, Any], generated: object, model: str) -> dict[str, Any]:
    """Attach the DeepSeek generation call's safe token/cost counters to a node step, if reported."""
    counters = generated.usage if isinstance(generated, GenerationResult) else None
    usage = usage_from_counters(counters, model)
    if usage is not None:
        step["tokens"] = usage.total_tokens
        step["cost_usd"] = usage.cost_usd
    return step


def build_graph(
    config: AgentConfig,
    *,
    token_callback: Callable[[str], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    stream_started: Callable[[Callable[[], None]], None] | None = None,
) -> Any:
    """Compile the agent graph with routing, retrieval, and tools bound to ``config``.

    Config is bound via closures, never placed in graph state, so provider keys never enter the
    checkpointer. Compilation validates the graph structure and fails clearly on a bad topology.
    """

    def receive_question(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        if not state["question"].strip():
            return {
                "route": "reject",
                "error": "empty_question",
                "steps": [_step(state, "receive_question", "error", started, notes="empty question")],
            }
        return {"steps": [_step(state, "receive_question", "ok", started, notes=None)]}

    def guardrail_input_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        decision = validate_input(state["question"], state.get("jurisdiction"))
        if decision.action != "allow":
            return {
                "route": "reject",
                "answer": decision.answer,
                "guardrail_events": [decision.event.as_dict()] if decision.event else [],
                "steps": [_step(state, "guardrail_input", "ok", started, notes=f"outcome={decision.action}")],
            }
        return {"steps": [_step(state, "guardrail_input", "ok", started, notes="outcome=allowed")]}

    def route_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        decision = (
            route_question(state["question"], config)
            if state["route_preference"] == "auto"
            else route_question(state["question"], config, state["route_preference"])
        )
        step = _step(state, "route", "ok", started, notes=f"route={decision.route}")
        if decision.usage is not None:
            step["tokens"] = decision.usage.total_tokens
            step["cost_usd"] = decision.usage.cost_usd
        return {
            "route": decision.route,
            "ticket_id": decision.ticket_id,
            "steps": [step],
        }

    def retrieve_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        if state.get("jurisdiction") not in {"US", "ES"}:
            return {
                "route": "reject",
                "answer": JURISDICTION_REQUIRED,
                "guardrail_events": [
                    {
                        "layer": "retrieval",
                        "rule_id": "jurisdiction_missing",
                        "category": "security",
                        "outcome": "clarification",
                        "duration_ms": 0,
                    }
                ],
                "steps": [_step(state, "retrieve", "error", started, notes="jurisdiction missing")],
            }
        try:
            chunks = retrieve(state["question"], config=config.rag, jurisdiction=state.get("jurisdiction"))
        except Exception as exc:
            logger.warning("agent_retrieve_failed error_type=%s", type(exc).__name__)
            return {
                "retrieved": [],
                "error": "retrieval_failed",
                "steps": [_step(state, "retrieve", "error", started, notes="retrieval failed")],
            }
        safe_chunks = [chunk for chunk in chunks if evidence_is_safe(str(chunk.get("text", "")))]
        events: list[dict[str, Any]] = []
        if len(safe_chunks) != len(chunks):
            events.append(
                {
                    "layer": "evidence",
                    "rule_id": "retrieved_instruction",
                    "category": "security",
                    "outcome": "blocked",
                    "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
                }
            )
        return {
            "retrieved": safe_chunks,
            "guardrail_events": events,
            "steps": [_step(state, "retrieve", "ok", started, notes=f"chunks={len(safe_chunks)}")],
        }

    def ticket_tool_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        ticket_id = state.get("ticket_id")
        if not validate_ticket_argument(ticket_id):
            block = {"source_document": "ticket", "section": "status", "text": "No ticket id was provided."}
            call = {"tool_name": "ticket_status", "status": "error", "duration_ms": 0, "error_type": "missing_id"}
            return {
                "tool_context": [block],
                "tool_calls": [call],
                "steps": [_step(state, "ticket_tool", "error", started, notes="missing ticket id")],
            }

        assert isinstance(ticket_id, int)
        result = lookup_ticket_status(ticket_id, config)
        if result.outcome == "ok" and result.ticket is not None:
            ticket = result.ticket
            text = (
                f"Ticket {ticket.ticket_id}: status={ticket.status}, category={ticket.category}, "
                f"opened {ticket.created_at}, last updated {ticket.updated_at}."
            )
            call_status, step_status, notes = "ok", "ok", f"status={ticket.status}"
        elif result.outcome == "not_found":
            text = f"Ticket {ticket_id} was not found in the incident system."
            call_status, step_status, notes = "ok", "ok", "not_found"
        else:  # timeout | error -> honest fallback, never a fabricated status
            text = (
                f"The current status of ticket {ticket_id} could not be confirmed right now. "
                "Tell the user you couldn't confirm it and to try again shortly."
            )
            call_status = "timeout" if result.outcome == "timeout" else "error"
            step_status, notes = "error", result.outcome

        block = {"source_document": f"ticket-{ticket_id}", "section": "status", "text": text}
        call = {
            "tool_name": "ticket_status",
            "status": call_status,
            "duration_ms": result.duration_ms,
            "error_type": None if call_status == "ok" else result.outcome,
        }
        if not evidence_is_safe(text):
            block = {"source_document": "ticket", "section": "status", "text": "Tool evidence was blocked."}
            call["status"] = "denied"
            return {
                "tool_context": [block],
                "tool_calls": [call],
                "guardrail_events": [
                    {
                        "layer": "evidence",
                        "rule_id": "tool_instruction",
                        "category": "security",
                        "outcome": "blocked",
                        "duration_ms": result.duration_ms,
                    }
                ],
                "steps": [_step(state, "ticket_tool", "error", started, notes="unsafe tool evidence")],
            }
        return {
            "tool_context": [block],
            "tool_calls": [call],
            "authoritative_status": result.ticket.status if result.ticket else None,
            "steps": [_step(state, "ticket_tool", step_status, started, notes=notes)],
        }

    def usable_memory(state: AgentState) -> tuple[list[dict[str, object]], list[dict[str, Any]]]:
        current = list(state.get("retrieved") or []) + list(state.get("tool_context") or [])
        current_text = " ".join(str(chunk.get("text", "")) for chunk in current).casefold()
        current_subjects = {str(chunk.get("subject_key")) for chunk in current if chunk.get("subject_key")}
        usable: list[dict[str, object]] = []
        omitted = False
        for memory in state.get("memory_evidence") or []:
            carrier_name = str(memory.get("carrier_name", "")).casefold()
            subject_key = str(memory.get("subject_key", ""))
            conflict = subject_key in current_subjects or bool(carrier_name and carrier_name in current_text)
            if conflict or not evidence_is_safe(str(memory.get("text", ""))):
                omitted = True
                continue
            usable.append(memory)
        events = (
            [
                {
                    "layer": "memory",
                    "rule_id": "memory_authority_omitted",
                    "category": "content",
                    "outcome": "blocked",
                    "duration_ms": 0,
                }
            ]
            if omitted
            else []
        )
        return usable, events

    def guarded_token_callback(
        state: AgentState,
        *,
        has_grounded_evidence: bool,
        blocked: list[str],
    ) -> Callable[[str], None] | None:
        if token_callback is None:
            return None
        streamed: list[str] = []

        def emit(delta: str) -> None:
            streamed.append(delta)
            rule_id = validate_output(
                "".join(streamed),
                state.get("jurisdiction"),
                authoritative_status=state.get("authoritative_status"),
                has_grounded_evidence=has_grounded_evidence,
            )
            if rule_id:
                blocked.append(rule_id)
                raise GenerationCancelled("streaming output blocked")
            token_callback(delta)

        return emit

    def blocked_stream_result(state: AgentState, started: float, rule_id: str) -> dict[str, Any]:
        if token_callback is not None:
            token_callback(OUTPUT_FALLBACK)
        return {
            "answer": OUTPUT_FALLBACK,
            "route": "reject",
            "guardrail_events": [
                {
                    "layer": "output",
                    "rule_id": rule_id,
                    "category": "content",
                    "outcome": "blocked",
                    "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
                }
            ],
            "steps": [_step(state, "generate", "ok", started, notes="stream blocked")],
        }

    def generate_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        memory, events = usable_memory(state)
        context = list(state.get("retrieved") or []) + list(state.get("tool_context") or []) + memory
        blocked: list[str] = []
        try:
            generated = generate_answer(
                state["question"],
                context,
                config.rag,
                jurisdiction=state.get("jurisdiction"),
                include_memory_candidate=True,
                token_callback=guarded_token_callback(
                    state,
                    has_grounded_evidence=bool(context),
                    blocked=blocked,
                ),
                cancelled=cancelled,
                stream_started=stream_started,
            )
        except GenerationCancelled:
            if blocked:
                return blocked_stream_result(state, started, blocked[0])
            raise
        except Exception as exc:
            logger.warning("agent_generate_failed error_type=%s", type(exc).__name__)
            return {
                "error": "generation_failed",
                "steps": [_step(state, "generate", "error", started, notes="generation failed")],
            }
        answer = generated.answer if isinstance(generated, GenerationResult) else generated
        candidate = generated.memory_candidate if isinstance(generated, GenerationResult) else None
        step = _record_generation_usage(
            _step(state, "generate", "ok", started, notes="grounded answer"), generated, config.rag.generation_model
        )
        return {
            "answer": answer,
            "memory_candidate": candidate,
            "guardrail_events": events,
            "steps": [step],
        }

    def no_context_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        memory, events = usable_memory(state)
        blocked: list[str] = []
        try:
            generated = generate_answer(
                state["question"],
                memory,
                config.rag,
                jurisdiction=state.get("jurisdiction"),
                include_memory_candidate=True,
                token_callback=guarded_token_callback(
                    state,
                    has_grounded_evidence=bool(memory),
                    blocked=blocked,
                ),
                cancelled=cancelled,
                stream_started=stream_started,
            )
        except GenerationCancelled:
            if blocked:
                return blocked_stream_result(state, started, blocked[0])
            raise
        except Exception as exc:
            logger.warning("agent_no_context_failed error_type=%s", type(exc).__name__)
            return {
                "error": "generation_failed",
                "steps": [_step(state, "no_context", "error", started, notes="generation failed")],
            }
        answer = generated.answer if isinstance(generated, GenerationResult) else generated
        candidate = generated.memory_candidate if isinstance(generated, GenerationResult) else None
        step = _record_generation_usage(
            _step(state, "no_context", "ok", started, notes="no current context"),
            generated,
            config.rag.generation_model,
        )
        return {
            "answer": answer,
            "memory_candidate": candidate,
            "guardrail_events": events,
            "steps": [step],
        }

    def guardrail_output_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        answer = state.get("answer") or ""
        memory, _events = usable_memory(state)
        rule_id = validate_output(
            answer,
            state.get("jurisdiction"),
            authoritative_status=state.get("authoritative_status"),
            has_grounded_evidence=bool(state.get("retrieved") or state.get("tool_context") or memory),
        )
        if rule_id:
            return {
                "answer": OUTPUT_FALLBACK,
                "route": "reject",
                "guardrail_events": [
                    {
                        "layer": "output",
                        "rule_id": rule_id,
                        "category": "content",
                        "outcome": "blocked",
                        "duration_ms": max(0, int((time.perf_counter() - started) * 1000)),
                    }
                ],
                "steps": [_step(state, "guardrail_output", "ok", started, notes="outcome=blocked")],
            }
        return {"steps": [_step(state, "guardrail_output", "ok", started, notes="outcome=allowed")]}

    def memory_selfeval_node(state: AgentState) -> dict[str, Any]:
        started = time.perf_counter()
        outcome = "candidate" if state.get("memory_candidate") is not None else "none"
        return {"steps": [_step(state, "memory_selfeval", "ok", started, notes=f"outcome={outcome}")]}

    def after_receive(state: AgentState) -> str:
        return "reject" if state.get("route") == "reject" else "guardrail_input"

    def after_input(state: AgentState) -> str:
        return "reject" if state.get("route") == "reject" else "route"

    def after_route(state: AgentState) -> str:
        return "ticket_tool" if state["route"] == "ticket" else "retrieve"

    def after_retrieve(state: AgentState) -> str:
        if state.get("route") == "reject":
            return "end"
        if state.get("error"):
            return "end"
        if state["route"] == "both":
            return "ticket_tool"
        return "generate" if state.get("retrieved") else "no_context"

    def after_output(state: AgentState) -> str:
        return "end" if state.get("route") == "reject" else "memory_selfeval"

    graph = StateGraph(AgentState)
    graph.add_node("receive_question", receive_question)
    graph.add_node("guardrail_input", guardrail_input_node)
    graph.add_node("route", route_node)
    graph.add_node("retrieve", retrieve_node)
    graph.add_node("ticket_tool", ticket_tool_node)
    graph.add_node("generate", generate_node)
    graph.add_node("no_context", no_context_node)
    graph.add_node("guardrail_output", guardrail_output_node)
    graph.add_node("memory_selfeval", memory_selfeval_node)

    graph.add_edge(START, "receive_question")
    graph.add_conditional_edges(
        "receive_question", after_receive, {"reject": END, "guardrail_input": "guardrail_input"}
    )
    graph.add_conditional_edges("guardrail_input", after_input, {"reject": END, "route": "route"})
    graph.add_conditional_edges("route", after_route, {"retrieve": "retrieve", "ticket_tool": "ticket_tool"})
    graph.add_conditional_edges(
        "retrieve",
        after_retrieve,
        {"ticket_tool": "ticket_tool", "generate": "generate", "no_context": "no_context", "end": END},
    )
    graph.add_edge("ticket_tool", "generate")
    graph.add_edge("generate", "guardrail_output")
    graph.add_edge("no_context", "guardrail_output")
    graph.add_conditional_edges(
        "guardrail_output",
        after_output,
        {"end": END, "memory_selfeval": "memory_selfeval"},
    )
    graph.add_edge("memory_selfeval", END)

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


def run_agent(
    question: str,
    config: AgentConfig,
    jurisdiction: str | None = None,
    memory_evidence: list[dict[str, object]] | None = None,
    route_preference: Literal["auto", "knowledge", "ticket"] = "auto",
    token_callback: Callable[[str], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
    stream_started: Callable[[Callable[[], None]], None] | None = None,
) -> AgentRunResult:
    """Invoke the compiled graph once and return a structured, persistable run result."""
    graph = build_graph(
        config,
        token_callback=token_callback,
        cancelled=cancelled,
        stream_started=stream_started,
    )
    trace_id = uuid4().hex
    started_at = _utc_now()
    perf_start = time.perf_counter()

    initial: AgentState = {
        "question": question,
        "trace_id": trace_id,
        "agent_name": config.agent_name,
        "jurisdiction": jurisdiction,
        "route_preference": route_preference,
        "route": "",
        "ticket_id": None,
        "retrieved": None,
        "memory_evidence": memory_evidence or [],
        "memory_candidate": None,
        "tool_context": [],
        "tool_calls": [],
        "answer": None,
        "authoritative_status": None,
        "guardrail_events": [],
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
        guardrail_events=final.get("guardrail_events", []),
        memory_candidate=final.get("memory_candidate"),
    )
