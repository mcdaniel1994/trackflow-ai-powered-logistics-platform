"""The RFP intake & routing graph (Engagement 9, Phase 1).

A LangGraph orchestrator-worker-synthesizer flow over the converted Markdown:

    START → classify ─not-rfp→ END(discarded)
                     └─rfp──→ extract → orchestrate → workers → synthesize → END(routed)

The graph is pure: it operates on Markdown text and returns an ``IntakeOutcome`` (classification,
safe metadata, per-department key aspects, and a node trace). The service persists the outcome and
records the trace in the Engagement 8 trace store. Agent functions are imported as module-level
names so tests monkeypatch them without a live provider. Provider config is bound via closure and
never enters graph state.
"""

from __future__ import annotations

import operator
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import (
    RfpAgentError,
    classify_document,
    currency_for,
    extract_key_aspects,
    extract_metadata,
    plan_departments,
    synthesize_routing,
)
from .config import RfpConfig


class IntakeState(TypedDict, total=False):
    markdown: str
    is_rfp: bool
    discard_reason: str | None
    metadata: dict[str, Any] | None
    departments: list[str]
    department_aspects: dict[str, list[str]]
    routing_summary: dict[str, Any]
    error: str | None
    steps: Annotated[list[dict[str, Any]], operator.add]


@dataclass
class IntakeOutcome:
    """The result of one intake run; the service maps it to ticket + section updates."""

    status: str  # routed | discarded | error
    is_rfp: bool
    discard_reason: str | None
    metadata: dict[str, Any] | None
    departments: list[str]
    department_aspects: dict[str, list[str]]
    routing_summary: dict[str, Any]
    error: str | None
    steps: list[dict[str, Any]] = field(default_factory=list)


def _step(node: str, started: float, status: str, notes: str | None = None) -> dict[str, Any]:
    """A safe node-trace entry in the Engagement 8 recorder format (no content)."""
    now = time.time()
    return {
        "node_name": node,
        "status": status,
        "started_at": _iso(started),
        "ended_at": _iso(now),
        "duration_ms": int((now - started) * 1000),
        "tokens": None,
        "cost_usd": None,
        "notes": notes,
    }


def _iso(epoch: float) -> str:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(epoch, tz=UTC).isoformat()


def build_intake_graph(config: RfpConfig) -> Any:
    """Compile the intake graph with provider config bound via closure (kept out of state)."""

    def classify_node(state: IntakeState) -> IntakeState:
        started = time.time()
        try:
            result = classify_document(state["markdown"], config)
        except RfpAgentError as exc:
            return {"error": exc.detail, "steps": [_step("classify", started, "error")]}
        if not result.is_rfp:
            return {
                "is_rfp": False,
                "discard_reason": result.reason,
                "steps": [_step("classify", started, "ok", "not_rfp")],
            }
        return {"is_rfp": True, "steps": [_step("classify", started, "ok", "rfp")]}

    def extract_node(state: IntakeState) -> IntakeState:
        started = time.time()
        try:
            meta = extract_metadata(state["markdown"], config)
        except RfpAgentError as exc:
            return {"error": exc.detail, "steps": [_step("extract_metadata", started, "error")]}
        return {
            "metadata": {
                "client_name": meta.client_name,
                "client_country": meta.client_country,
                "currency": currency_for(meta.client_country),
                "services_requested": meta.services_requested,
                "monthly_volume": meta.monthly_volume,
                "deadline_days": meta.deadline_days,
                "budget_range": meta.budget_range,
            },
            "steps": [_step("extract_metadata", started, "ok")],
        }

    def orchestrate_node(state: IntakeState) -> IntakeState:
        started = time.time()
        metadata = state.get("metadata") or {}
        departments = plan_departments(list(metadata.get("services_requested", [])))
        return {
            "departments": departments,
            "steps": [_step("orchestrate", started, "ok", f"departments={len(departments)}")],
        }

    def workers_node(state: IntakeState) -> IntakeState:
        started = time.time()
        aspects: dict[str, list[str]] = {}
        try:
            for department in state.get("departments", []):
                aspects[department] = extract_key_aspects(department, state["markdown"], config)
        except RfpAgentError as exc:
            return {"error": exc.detail, "steps": [_step("workers", started, "error")]}
        return {
            "department_aspects": aspects,
            "steps": [_step("workers", started, "ok", f"workers={len(aspects)}")],
        }

    def synthesize_node(state: IntakeState) -> IntakeState:
        started = time.time()
        summary = synthesize_routing(state.get("department_aspects", {}))
        return {"routing_summary": summary, "steps": [_step("synthesize", started, "ok")]}

    def after_classify(state: IntakeState) -> str:
        if state.get("error"):
            return "end"
        return "extract" if state.get("is_rfp") else "end"

    def after_node(state: IntakeState) -> str:
        return "end" if state.get("error") else "continue"

    graph = StateGraph(IntakeState)
    graph.add_node("classify", classify_node)
    graph.add_node("extract", extract_node)
    graph.add_node("orchestrate", orchestrate_node)
    graph.add_node("workers", workers_node)
    graph.add_node("synthesize", synthesize_node)

    graph.add_edge(START, "classify")
    graph.add_conditional_edges("classify", after_classify, {"extract": "extract", "end": END})
    graph.add_conditional_edges("extract", after_node, {"continue": "orchestrate", "end": END})
    graph.add_edge("orchestrate", "workers")
    graph.add_conditional_edges("workers", after_node, {"continue": "synthesize", "end": END})
    graph.add_edge("synthesize", END)
    return graph.compile()


def run_intake(markdown: str, config: RfpConfig) -> IntakeOutcome:
    """Run the intake graph and return a structured outcome with a safe node trace."""
    graph = build_intake_graph(config)
    final: IntakeState = graph.invoke({"markdown": markdown})

    steps = final.get("steps", [])
    for sequence, step in enumerate(steps, start=1):
        step["sequence"] = sequence

    if final.get("error"):
        status = "error"
    elif final.get("is_rfp") is False:
        status = "discarded"
    else:
        status = "routed"

    return IntakeOutcome(
        status=status,
        is_rfp=bool(final.get("is_rfp", False)),
        discard_reason=final.get("discard_reason"),
        metadata=final.get("metadata"),
        departments=list(final.get("departments", [])),
        department_aspects=dict(final.get("department_aspects", {})),
        routing_summary=dict(final.get("routing_summary", {})),
        error=final.get("error"),
        steps=steps,
    )
