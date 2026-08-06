"""Per-department section generation and the generator-evaluator loop (Engagement 9, Phase 2).

Each active department drafts its section with the Engagement 7 DeepSeek generator
(``generate_answer``), then three deterministic evaluators score it. A failing section is redrafted
with concrete feedback, up to a hard iteration cap, so the loop can never run forever. Runs off the
request path in its own session; a section that never passes is left for a human (Phase 3), not
discarded. Traces are content-free and reuse the Engagement 8 trace store.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from pipelines.rag import RagConfig, RagPipelineError, complete, retrieve  # type: ignore[import-untyped]
from sqlmodel import Session

from ...db.session import get_engine
from ..agents.graph import AgentRunResult
from ..agents.recorder import persist_run
from .evaluators import evaluate_section
from .models import RfpDepartmentSection, RfpTicket, utc_now
from .repository import RfpRepository

logger = logging.getLogger(__name__)

GENERATION_AGENT_NAME = "trackflow-rfp-generation"

_GUIDELINES = (
    "Quote only in the client's currency. State the on-time delivery SLA as a percentage. Never "
    "promise returns processing in under 48 hours. Include a volume-based discount tier table. Never "
    "disclose negotiated carrier rates — only the final price to the client."
)

# A drafting-oriented system prompt: unlike the knowledge assistant, the RFP writer composes proposal
# terms (SLA %, discount tiers, client prices) that a human approves next. Service facts are grounded
# in the retrieved TrackFlow policy context; the business rules below are hard constraints.
_DRAFTING_SYSTEM_PROMPT = (
    "You are a TrackFlow proposal writer drafting ONE department section of a B2B logistics pricing "
    "proposal. A human account manager reviews and approves your draft next, so you should compose "
    "concrete commercial terms rather than refuse. Write in a confident, professional proposal voice "
    "with short, readable sentences.\n\n"
    "Ground service facts — delivery windows, storage rates, returns handling, carrier coverage — in "
    "the TrackFlow policy context provided. Where the context gives a figure, use it; otherwise propose "
    "reasonable, clearly-labelled draft terms consistent with that policy for the human to confirm.\n\n"
    "Every section MUST:\n"
    "- Quote all prices only in {currency} using the {symbol} symbol; never use any other currency.\n"
    "- State an on-time delivery SLA as a percentage (for example '98% on-time delivery').\n"
    "- Include a volume-based discount tier table and use the words 'volume' and 'discount tier'.\n\n"
    "Every section MUST NOT:\n"
    "- Promise returns processing in under 48 hours; note international returns are handled manually "
    "by Sofía Ramos's team.\n"
    "- Disclose negotiated or internal carrier rates — quote only the final price to the client.\n"
    "- Grant a storage discount on your own authority — note it requires Miguel Torres's approval.\n\n"
    "Return only the section text."
)

_CURRENCY_SYMBOL = {"USD": "$", "EUR": "€"}


def _aspects(section: RfpDepartmentSection) -> list[str]:
    raw = (section.key_aspects or {}).get("aspects", [])
    return [str(item) for item in raw] if isinstance(raw, list) else []


def _grounding(
    department_id: str, country: str | None, key_aspects: list[str], rag_config: RagConfig
) -> list[dict[str, object]]:
    """Retrieve policy-corpus chunks so the section is grounded in real TrackFlow facts.

    Without grounding the reused Engagement 7 generator (anti-invention system prompt) refuses with
    "I don't have that information documented"; retrieval gives it the real SLA, returns, storage and
    carrier-coverage policy to draft from. Best-effort: an empty result still yields an honest draft.
    """
    jurisdiction = country if country in {"US", "ES"} else None
    query = (
        f"TrackFlow {department_id} logistics services for a B2B client: delivery SLA percentage, "
        f"returns policy, storage pricing, carrier coverage. "
        f"Client priorities: {', '.join(key_aspects) or 'standard fulfilment'}."
    )
    return cast("list[dict[str, object]]", retrieve(query, config=rag_config, jurisdiction=jurisdiction))


def draft_section(
    department_id: str,
    *,
    country: str | None,
    currency: str | None,
    volume: int | None,
    key_aspects: list[str],
    feedback: list[str],
    rag_config: RagConfig,
) -> str:
    """Draft one department's section from explicit fields (usable by intake and the approval loop)."""
    context = (
        f"Client country: {country or 'unknown'}. Currency: {currency or 'unknown'}. "
        f"Monthly volume: {volume or 'unknown'}. Key aspects: {', '.join(key_aspects) or 'none'}."
    )
    fix = f" Revise the draft to fix these issues: {', '.join(feedback)}." if feedback else ""
    chunks = _grounding(department_id, country, key_aspects, rag_config)
    grounding = _format_grounding(chunks)
    currency_code = currency or "USD"
    system_prompt = _DRAFTING_SYSTEM_PROMPT.format(
        currency=currency_code, symbol=_CURRENCY_SYMBOL.get(currency_code, "$")
    )
    user_content = (
        f"Draft the {department_id} section of a TrackFlow logistics pricing proposal.\n"
        f"{context}\n\n"
        f"Follow these rules exactly: {_GUIDELINES}{fix}\n\n"
        f"<trackflow_policy_context>\n{grounding}\n</trackflow_policy_context>"
    )
    return str(complete(system_prompt, user_content, rag_config))


def _format_grounding(chunks: list[dict[str, object]]) -> str:
    if not chunks:
        return "No specific policy excerpts were retrieved; draft from standard TrackFlow logistics practice."
    blocks = []
    for index, chunk in enumerate(chunks, start=1):
        source = chunk.get("source_document", "policy")
        section = chunk.get("section", "")
        text = chunk.get("text", "")
        blocks.append(f"[{index}] ({source} — {section})\n{text}")
    return "\n\n".join(blocks)


def generate_section(
    department_id: str,
    ticket: RfpTicket,
    key_aspects: list[str],
    feedback: list[str],
    rag_config: RagConfig,
) -> str:
    """Draft one department's proposal section for a ticket with the DeepSeek generator."""
    return draft_section(
        department_id,
        country=ticket.client_country,
        currency=ticket.currency,
        volume=ticket.monthly_volume,
        key_aspects=key_aspects,
        feedback=feedback,
        rag_config=rag_config,
    )


def run_generation_for_ticket(ticket_id: str, rag_config: RagConfig, max_iterations: int, *, env: str) -> None:
    """Generate and evaluate every department section, then advance the ticket. Never raises."""
    try:
        engine = get_engine()
        steps: list[dict[str, Any]] = []
        with Session(engine) as session:
            repo = RfpRepository(session)
            ticket = repo.get(ticket_id)
            if ticket is None or ticket.status != "drafting":
                return  # only a freshly-routed ticket is generated (idempotency guard)
            sections = repo.sections_for_ticket(ticket_id)
            for section in sections:
                steps.append(_generate_one(ticket, section, rag_config, max_iterations))
            ticket.status = "under_evaluation"
            ticket.updated_at = utc_now()
            repo.save(ticket)
            for section in sections:
                section.updated_at = utc_now()
            repo.add_sections(sections)
    except Exception as exc:  # a background worker must never crash the process
        logger.warning("rfp_generation_failed error_type=%s", type(exc).__name__)
        return
    _record_trace(steps, env=env)


def _generate_one(
    ticket: RfpTicket,
    section: RfpDepartmentSection,
    rag_config: RagConfig,
    max_iterations: int,
) -> dict[str, Any]:
    started = time.time()
    aspects = _aspects(section)
    feedback: list[str] = []
    draft = ""
    passed = False
    iteration = 0
    for iteration in range(1, max(1, max_iterations) + 1):
        try:
            draft = generate_section(section.department_id, ticket, aspects, feedback, rag_config)
        except RagPipelineError:
            section.draft_content = None
            section.evaluation_results = {"error": True}
            section.iteration_count = iteration
            return _step(f"generate:{section.department_id}", started, "error")
        evaluation = evaluate_section(
            draft, currency=ticket.currency, department_id=section.department_id, key_aspects=aspects
        )
        feedback = evaluation.issues
        passed = evaluation.passed
        if passed:
            section.evaluation_results = {**evaluation.results, "passed": True, "iterations": iteration}
            break
        section.evaluation_results = {**evaluation.results, "passed": False, "iterations": iteration}
    section.draft_content = draft
    section.iteration_count = iteration
    notes = "passed" if passed else "needs_human"
    return _step(f"generate:{section.department_id}", started, "ok", notes)


def _step(node: str, started: float, status: str, notes: str | None = None) -> dict[str, Any]:
    now = time.time()
    return {
        "node_name": node,
        "status": status,
        "started_at": datetime.fromtimestamp(started, tz=UTC).isoformat(),
        "ended_at": datetime.fromtimestamp(now, tz=UTC).isoformat(),
        "duration_ms": int((now - started) * 1000),
        "tokens": None,
        "cost_usd": None,
        "notes": notes,
    }


def _record_trace(steps: list[dict[str, Any]], *, env: str) -> None:
    if not steps:
        return
    for sequence, step in enumerate(steps, start=1):
        step["sequence"] = sequence
    started = datetime.fromisoformat(steps[0]["started_at"])
    ended = datetime.fromisoformat(steps[-1]["ended_at"])
    result = AgentRunResult(
        trace_id=uuid4().hex,
        agent_name=GENERATION_AGENT_NAME,
        status="ok" if all(step["status"] == "ok" for step in steps) else "error",
        route_taken="generate",
        answer=None,
        started_at=started,
        ended_at=ended,
        duration_ms=sum(int(step.get("duration_ms") or 0) for step in steps),
        steps=steps,
        tool_calls=[],
    )
    persist_run(result, env=env, input_summary=None, output_summary=None)
