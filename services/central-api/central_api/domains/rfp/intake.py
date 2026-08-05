"""Background intake runner: convert-outcome → ticket state, then record a safe trace.

Runs off the request path (FastAPI ``BackgroundTasks``) in its own short-lived session, mirroring the
Engagement 8 recorder. It applies the graph ``IntakeOutcome`` to the ticket and its department
sections, then persists a node trace to the Engagement 8 trace store. Every failure is swallowed so a
trace-store or DB hiccup never crashes a background worker; the ticket simply stays where it is.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import uuid4

from sqlmodel import Session

from ...db.session import get_engine
from ..agents.graph import AgentRunResult
from ..agents.recorder import persist_run
from .config import RfpConfig
from .graph import IntakeOutcome, run_intake
from .models import RfpDepartmentSection, RfpTicket, utc_now
from .repository import RfpRepository

logger = logging.getLogger(__name__)

INTAKE_AGENT_NAME = "trackflow-rfp-intake"


def run_intake_for_ticket(ticket_id: str, config: RfpConfig, *, env: str) -> None:
    """Convert intake results into ticket state and a safe trace. Never raises."""
    try:
        engine = get_engine()
        with Session(engine) as session:
            repo = RfpRepository(session)
            ticket = repo.get(ticket_id)
            if ticket is None:
                return
            outcome = run_intake(ticket.markdown_text or "", config)
            _apply_outcome(repo, ticket, outcome)
    except Exception as exc:  # a background worker must never crash the process
        logger.warning("rfp_intake_failed error_type=%s", type(exc).__name__)
        return
    _record_trace(outcome, env=env)


def _apply_outcome(repo: RfpRepository, ticket: RfpTicket, outcome: IntakeOutcome) -> None:
    ticket.updated_at = utc_now()
    if outcome.status == "discarded":
        ticket.status = "discarded"
        ticket.discard_reason = outcome.discard_reason
        repo.save(ticket)
        return
    if outcome.status == "error":
        # Leave the ticket in ``analyzing`` so a later phase can reprocess; record only the trace.
        repo.save(ticket)
        return

    metadata = outcome.metadata or {}
    ticket.client_name = metadata.get("client_name")
    ticket.client_country = metadata.get("client_country")
    ticket.currency = metadata.get("currency")
    ticket.services_requested = list(metadata.get("services_requested", []))
    ticket.monthly_volume = metadata.get("monthly_volume")
    ticket.deadline_days = metadata.get("deadline_days")
    ticket.budget_range = metadata.get("budget_range")
    ticket.departments_needed = list(outcome.departments)
    ticket.status = "drafting"
    repo.save(ticket)
    repo.add_sections(
        [
            RfpDepartmentSection(
                ticket_id=ticket.id,
                department_id=department,
                approval_status="pending",
                key_aspects={"aspects": outcome.department_aspects.get(department, [])},
            )
            for department in outcome.departments
        ]
    )


def _record_trace(outcome: IntakeOutcome, *, env: str) -> None:
    steps = outcome.steps
    started = _parse(steps[0]["started_at"]) if steps else utc_now()
    ended = _parse(steps[-1]["ended_at"]) if steps else started
    duration_ms = sum(int(step.get("duration_ms") or 0) for step in steps)
    result = AgentRunResult(
        trace_id=uuid4().hex,
        agent_name=INTAKE_AGENT_NAME,
        status="ok" if outcome.status in ("routed", "discarded") else "error",
        route_taken=outcome.status,
        answer=None,
        started_at=started,
        ended_at=ended,
        duration_ms=duration_ms,
        steps=steps,
        tool_calls=[],
    )
    # Content-free by design: no summaries, no markdown, no prompts.
    persist_run(result, env=env, input_summary=None, output_summary=None)


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value)
