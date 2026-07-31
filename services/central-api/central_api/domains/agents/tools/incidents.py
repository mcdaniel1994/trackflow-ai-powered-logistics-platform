"""Support-ticket status lookup tool (Part 2, required tool).

Reads the CURRENT status of an Incidents Manager ticket. Because the agent runs inside central-api,
this calls ``IncidentService`` in-process against the live database (never simulated or hardcoded
data) — Part 3 swaps this implementation for the OAuth-protected MCP server without changing the
graph node. Typed input (``ticket_id``) and output (``TicketStatus``), an explicit timeout, and
typed outcomes so the caller can emit an honest fallback instead of a fabricated status.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeout
from dataclasses import dataclass

from sqlmodel import Session

from ....db.session import get_engine
from ...incidents.service import IncidentError, IncidentService

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class TicketStatus:
    """The safe, current facts about one ticket (no free-text title/description)."""

    ticket_id: int
    status: str
    category: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TicketLookupResult:
    """Typed outcome of a lookup. ``ticket`` is set only when ``outcome == 'ok'``."""

    outcome: str  # ok | not_found | timeout | error
    ticket: TicketStatus | None
    duration_ms: int


def _fetch(ticket_id: int) -> TicketStatus:
    with Session(get_engine()) as session:
        read = IncidentService(session).get(ticket_id)
        return TicketStatus(
            ticket_id=read.id,
            status=str(read.status),
            category=str(read.category),
            created_at=read.created_at.isoformat(),
            updated_at=read.updated_at.isoformat(),
        )


def lookup_ticket_status(ticket_id: int, *, timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> TicketLookupResult:
    """Look up one ticket's current status with an explicit timeout and typed outcomes."""
    start = time.perf_counter()

    def _elapsed() -> int:
        return max(0, int((time.perf_counter() - start) * 1000))

    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            ticket = executor.submit(_fetch, ticket_id).result(timeout=timeout_seconds)
        return TicketLookupResult("ok", ticket, _elapsed())
    except FuturesTimeout:
        logger.warning("ticket_lookup_timeout ticket_id=%s", ticket_id)
        return TicketLookupResult("timeout", None, _elapsed())
    except IncidentError as exc:
        outcome = "not_found" if exc.status_code == 404 else "error"
        logger.warning("ticket_lookup_failed ticket_id=%s outcome=%s", ticket_id, outcome)
        return TicketLookupResult(outcome, None, _elapsed())
    except Exception as exc:
        logger.warning("ticket_lookup_error ticket_id=%s error_type=%s", ticket_id, type(exc).__name__)
        return TicketLookupResult("error", None, _elapsed())
