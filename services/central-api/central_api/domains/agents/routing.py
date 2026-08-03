"""Automatic routing: does the question need the knowledge base, a live ticket lookup, or both?

The agent decides on its own, without the user specifying (Part 2). An OpenAI model classifies the
question and extracts a ticket id when present; if the provider is unavailable it falls back to a
deterministic heuristic so the graph still routes sensibly (and so unit tests need no live key).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from .config import AgentConfig
from .pricing import ModelUsage, usage_from_message

logger = logging.getLogger(__name__)

_TICKET_RE = re.compile(r"(?:ticket|incident|case|order|#)\s*#?\s*(\d{1,9})", re.IGNORECASE)

_SYSTEM = (
    "You route a TrackFlow customer-experience question to the right source. Reply with a route:\n"
    "- 'ticket' when the user asks about the status of a specific support ticket/incident/order id.\n"
    "- 'rag' when the user asks about policies, returns, SLAs, carriers, or general procedures.\n"
    "- 'both' when they need a specific ticket's status AND policy context.\n"
    "Extract the numeric ticket id when the user names one; otherwise leave it null."
)


@dataclass(frozen=True)
class RouteDecision:
    route: str  # rag | ticket | both
    ticket_id: int | None
    usage: ModelUsage | None = None


class _RouteModel(BaseModel):
    route: Literal["rag", "ticket", "both"]
    ticket_id: int | None = None


def _heuristic(question: str) -> RouteDecision:
    match = _TICKET_RE.search(question)
    if match:
        return RouteDecision("ticket", int(match.group(1)))
    return RouteDecision("rag", None)


def route_question(question: str, config: AgentConfig) -> RouteDecision:
    """Classify the question and extract a ticket id, with a heuristic fallback."""
    api_key = config.rag.openai_api_key
    if not api_key:
        return _heuristic(question)

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(
            model=config.agent_model,
            api_key=api_key,
            temperature=0,
            timeout=config.route_timeout_seconds,
            max_retries=0,
        )
        response = llm.with_structured_output(_RouteModel, include_raw=True).invoke(
            [("system", _SYSTEM), ("human", question)]
        )
        response_map = response if isinstance(response, dict) else {}
        decision = response_map.get("parsed")
        raw = response_map.get("raw")
        route = decision.route if isinstance(decision, _RouteModel) else "rag"
        ticket_id = decision.ticket_id if isinstance(decision, _RouteModel) else None
        usage = usage_from_message(raw, config.agent_model)
    except Exception as exc:
        logger.warning("agent_route_llm_failed error_type=%s; using heuristic", type(exc).__name__)
        return _heuristic(question)

    # A tool route needs a concrete id: recover it heuristically, else fall back to RAG.
    if route in ("ticket", "both") and ticket_id is None:
        ticket_id = _heuristic(question).ticket_id
    if route in ("ticket", "both") and ticket_id is None:
        return RouteDecision("rag", None)
    return RouteDecision(route, ticket_id, usage)
