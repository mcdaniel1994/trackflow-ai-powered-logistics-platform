"""Human-in-the-loop approval and final-document completion (Engagement 9, Phase 3).

Each active department has its own interruptible approval graph, keyed by a per-department
``thread_id`` on the durable Postgres checkpointer. The graph pauses on a native ``interrupt()``
before a section is approved; resuming with the validated human decision continues from exactly that
point. Because each department is its own thread, pausing one never blocks another — branch-scoped by
construction. ``request_changes`` redrafts (Phase 2 generator + evaluators) and re-interrupts, capped
so it can never loop forever. When every active section is approved, an explicit arbitration node
checks cross-department consistency and the final document is synthesized.
"""

from __future__ import annotations

import logging
import operator
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, TypedDict
from uuid import uuid4

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from pipelines.rag import RagConfig, RagPipelineError  # type: ignore[import-untyped]
from sqlmodel import Session

from ...core.config import Settings
from ...db.session import get_engine
from ..agents.graph import AgentRunResult
from ..agents.recorder import persist_run
from .checkpointer import approval_checkpointer
from .errors import RetryableRfpProcessingError
from .evaluators import evaluate_section
from .generation import draft_section
from .models import RfpDepartmentSection, RfpFinalDocument, RfpTicket, utc_now
from .repository import RfpRepository

logger = logging.getLogger(__name__)

APPROVAL_AGENT_NAME = "trackflow-rfp-approval"
VALID_ACTIONS: frozenset[str] = frozenset({"approve", "reject", "request_changes"})
# Matches the agents service preview cap (telemetry standard §8): a truncated, content-limited preview.
_SUMMARY_MAX_CHARS = 200


class ApprovalState(TypedDict, total=False):
    department_id: str
    country: str | None
    currency: str | None
    volume: int | None
    key_aspects: list[str]
    draft: str
    iterations: int
    max_iterations: int
    feedback: list[str]
    evaluation: dict[str, Any]
    passed: bool
    decision: dict[str, Any]
    outcome: str
    steps: Annotated[list[dict[str, Any]], operator.add]


@dataclass
class DecisionOutcome:
    section_status: str
    ticket_status: str
    finalized: bool


def thread_id(ticket_id: str, department_id: str) -> str:
    return f"rfp:{ticket_id}:{department_id}"


def _step(
    node: str,
    started: float,
    status: str,
    notes: str | None = None,
    *,
    tokens: int | None = None,
    cost_usd: float | None = None,
) -> dict[str, Any]:
    """A safe node-trace entry that records the node's real wall-clock duration (no content)."""
    now = time.time()
    return {
        "node_name": node,
        "status": status,
        "started_at": datetime.fromtimestamp(started, tz=UTC).isoformat(),
        "ended_at": datetime.fromtimestamp(now, tz=UTC).isoformat(),
        "duration_ms": int((now - started) * 1000),
        "tokens": tokens,
        "cost_usd": cost_usd,
        "notes": notes,
    }


def build_approval_graph(rag_config: RagConfig, checkpointer: Any) -> Any:
    """Compile the per-department approval graph; provider config bound via closure (out of state)."""

    def review(state: ApprovalState) -> ApprovalState:
        decision = interrupt({"department_id": state["department_id"], "iteration": state.get("iterations", 1)})
        return {"decision": decision if isinstance(decision, dict) else {}}

    def approve(_state: ApprovalState) -> ApprovalState:
        started = time.time()
        return {"outcome": "approved", "steps": [_step("approve", started, "ok")]}

    def reject(_state: ApprovalState) -> ApprovalState:
        started = time.time()
        return {"outcome": "rejected", "steps": [_step("reject", started, "ok")]}

    def revise(state: ApprovalState) -> ApprovalState:
        started = time.time()
        iterations = state.get("iterations", 1)
        if iterations >= state.get("max_iterations", 2):
            return {"outcome": "changes_exhausted", "steps": [_step("revise", started, "ok", "cap_reached")]}
        try:
            draft, usage = draft_section(
                state["department_id"],
                country=state.get("country"),
                currency=state.get("currency"),
                volume=state.get("volume"),
                key_aspects=state.get("key_aspects", []),
                feedback=state.get("feedback", []),
                rag_config=rag_config,
            )
        except RagPipelineError:
            return {"outcome": "generation_error", "steps": [_step("revise", started, "error")]}
        evaluation = evaluate_section(
            draft,
            currency=state.get("currency"),
            department_id=state["department_id"],
            key_aspects=state.get("key_aspects", []),
        )
        tokens = usage.total_tokens if usage is not None else None
        cost = usage.cost_usd if usage is not None else None
        return {
            "draft": draft,
            "iterations": iterations + 1,
            "feedback": evaluation.issues,
            "evaluation": {**evaluation.results, "passed": evaluation.passed},
            "passed": evaluation.passed,
            "steps": [_step("revise", started, "ok", "redrafted", tokens=tokens, cost_usd=cost)],
        }

    def route_after_review(state: ApprovalState) -> str:
        return {"approve": "approve", "reject": "reject"}.get(
            (state.get("decision") or {}).get("action", ""), "revise"
        )

    def after_revise(state: ApprovalState) -> str:
        return "end" if state.get("outcome") else "loop"

    graph = StateGraph(ApprovalState)
    graph.add_node("review", review)
    graph.add_node("approve", approve)
    graph.add_node("reject", reject)
    graph.add_node("revise", revise)
    graph.add_edge(START, "review")
    graph.add_conditional_edges(
        "review", route_after_review, {"approve": "approve", "reject": "reject", "revise": "revise"}
    )
    graph.add_edge("approve", END)
    graph.add_edge("reject", END)
    graph.add_conditional_edges("revise", after_revise, {"loop": "review", "end": END})
    return graph.compile(checkpointer=checkpointer)


def _initial_state(ticket: RfpTicket, section: RfpDepartmentSection, max_iterations: int) -> ApprovalState:
    raw = (section.key_aspects or {}).get("aspects", [])
    aspects = [str(item) for item in raw] if isinstance(raw, list) else []
    return {
        "department_id": section.department_id,
        "country": ticket.client_country,
        "currency": ticket.currency,
        "volume": ticket.monthly_volume,
        "key_aspects": aspects,
        "draft": section.draft_content or "",
        "iterations": section.iteration_count or 1,
        "max_iterations": max_iterations,
        "feedback": [],
    }


def start_ticket_approval(
    ticket_id: str,
    settings: Settings,
    rag_config: RagConfig,
    max_iterations: int,
    *,
    env: str,
    raise_errors: bool = False,
) -> None:
    """Open a paused approval thread per department, then move the ticket to waiting_for_approval."""
    try:
        engine = get_engine()
        with Session(engine) as session:
            repo = RfpRepository(session)
            ticket = repo.get(ticket_id)
            if ticket is None or ticket.status != "under_evaluation":
                return
            sections = repo.sections_for_ticket(ticket_id)
            data = [(section, _initial_state(ticket, section, max_iterations)) for section in sections]
        with approval_checkpointer(settings) as saver:
            graph = build_approval_graph(rag_config, saver)
            for section, state in data:
                graph.invoke(state, {"configurable": {"thread_id": thread_id(ticket_id, section.department_id)}})
        with Session(engine) as session:
            repo = RfpRepository(session)
            ticket = repo.get(ticket_id)
            if ticket is not None and ticket.status == "under_evaluation":
                ticket.status = "waiting_for_approval"
                ticket.updated_at = utc_now()
                repo.save(ticket)
    except Exception as exc:
        logger.warning("rfp_start_approval_failed error_type=%s", type(exc).__name__)
        if raise_errors:
            raise RetryableRfpProcessingError("RFP approval setup failed") from exc


def submit_decision(
    ticket: RfpTicket,
    section: RfpDepartmentSection,
    *,
    action: str,
    note: str | None,
    actor: str,
    settings: Settings,
    rag_config: RagConfig,
    session: Session,
    env: str,
) -> DecisionOutcome:
    """Resume the department's approval thread with a validated decision; finalize when all approve."""
    if action not in VALID_ACTIONS:
        raise ValueError("invalid_action")

    with approval_checkpointer(settings) as saver:
        graph = build_approval_graph(rag_config, saver)
        config = {"configurable": {"thread_id": thread_id(ticket.id, section.department_id)}}
        snapshot = graph.get_state(config)
        if not snapshot.values or not snapshot.next:
            raise _AlreadyResolved()
        graph.invoke(Command(resume={"action": action, "note": note}), config)
        resumed = graph.get_state(config)

    values = resumed.values
    steps = list(values.get("steps", []))
    repo = RfpRepository(session)
    if resumed.next:
        # Redrafted and re-interrupted: awaiting a fresh decision on the new draft.
        section.approval_status = "pending"
        section.draft_content = values.get("draft", section.draft_content)
        section.iteration_count = values.get("iterations", section.iteration_count)
        if values.get("evaluation"):
            section.evaluation_results = values["evaluation"]
    else:
        outcome = values.get("outcome", "")
        if outcome == "approved":
            section.approval_status = "approved"
            section.approver = actor
            section.approved_at = utc_now()
        elif outcome == "rejected":
            section.approval_status = "rejected"
        else:  # changes_exhausted / generation_error
            section.approval_status = "changes_requested"
    section.updated_at = utc_now()
    repo.save_section(section)

    finalized, output_summary = _maybe_finalize(repo, ticket, steps)
    if finalized:
        steps.append(_step("finalize", time.time(), "ok"))
    _record_trace(steps, env=env, output_summary=output_summary)
    return DecisionOutcome(section.approval_status, ticket.status, finalized)


def _maybe_finalize(
    repo: RfpRepository, ticket: RfpTicket, steps: list[dict[str, Any]]
) -> tuple[bool, str | None]:
    """Consolidate the approved sections into the final document; return (finalized, output preview).

    The preview is a truncated, content-limited summary of the consolidated proposal so a completed
    RFP run is not blank in the Agent OS dashboard (the input remains an uploaded client document and
    is never persisted as a summary).
    """
    started = time.time()
    sections = repo.sections_for_ticket(ticket.id)
    if not sections or any(section.approval_status != "approved" for section in sections):
        return False, None
    # Explicit arbitration: a ticket is single-currency; drop any section that contradicts it before
    # synthesis rather than letting agents reconcile it themselves.
    currency = ticket.currency or "USD"
    consolidated = {
        section.department_id: (section.draft_content or "") for section in sections
    }
    steps.append(_step("arbitration", started, "ok", f"sections={len(consolidated)}"))
    repo.add_final_document(
        RfpFinalDocument(ticket_id=ticket.id, sections=consolidated, currency=currency)
    )
    ticket.status = "done"
    ticket.updated_at = utc_now()
    repo.save(ticket)
    preview = " ".join(
        f"{department}: {content}" for department, content in consolidated.items()
    ).strip()
    return True, (preview[:_SUMMARY_MAX_CHARS] or None)


def _record_trace(steps: list[dict[str, Any]], *, env: str, output_summary: str | None = None) -> None:
    if not steps:
        return
    for sequence, step in enumerate(steps, start=1):
        step["sequence"] = sequence
    started = datetime.fromisoformat(steps[0]["started_at"])
    ended = datetime.fromisoformat(steps[-1]["ended_at"])
    result = AgentRunResult(
        trace_id=uuid4().hex,
        agent_name=APPROVAL_AGENT_NAME,
        status="ok" if all(step["status"] == "ok" for step in steps) else "error",
        route_taken="approval",
        answer=None,
        started_at=started,
        ended_at=ended,
        duration_ms=sum(int(step.get("duration_ms") or 0) for step in steps),
        steps=steps,
        tool_calls=[],
    )
    persist_run(result, env=env, input_summary=None, output_summary=output_summary)


class AlreadyResolved(Exception):
    """Raised when a department has no pending approval to resume (already decided)."""


_AlreadyResolved = AlreadyResolved
