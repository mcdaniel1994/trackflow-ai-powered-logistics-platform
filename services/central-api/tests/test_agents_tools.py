"""Unit tests for the ticket tool and the routing heuristic (Part 2).

The tool's DB fetch is mocked, so these assert the timeout/outcome mapping and the no-key routing
heuristic without a live database or OpenAI key.
"""

from __future__ import annotations

import time

import pytest

from central_api.domains.agents.config import AgentConfig
from central_api.domains.agents.routing import RouteDecision, route_question
from central_api.domains.agents.tools import incidents
from central_api.domains.agents.tools.incidents import TicketStatus, lookup_ticket_status
from central_api.domains.incidents.service import IncidentError


class _RagCfg:
    min_score = 0.5
    openai_api_key = ""


def _config() -> AgentConfig:
    return AgentConfig(
        agent_name="a", rag=_RagCfg(), min_score=0.5,
        agent_model="gpt-4o-mini", route_timeout_seconds=8.0, ticket_timeout_seconds=5.0,
    )


def test_lookup_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    ticket = TicketStatus(42, "resolved", "lost_parcel", "2026-07-01T00:00:00+00:00", "2026-07-05T00:00:00+00:00")
    monkeypatch.setattr(incidents, "_fetch", lambda _id: ticket)
    result = lookup_ticket_status(42)
    assert result.outcome == "ok" and result.ticket == ticket


def test_lookup_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_404(_id: int) -> TicketStatus:
        raise IncidentError(404, "INCIDENT_NOT_FOUND", "Incident not found.")

    monkeypatch.setattr(incidents, "_fetch", raise_404)
    assert lookup_ticket_status(999).outcome == "not_found"


def test_lookup_service_error_is_not_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_503(_id: int) -> TicketStatus:
        raise IncidentError(503, "SERVICE_UNAVAILABLE", "down")

    monkeypatch.setattr(incidents, "_fetch", raise_503)
    assert lookup_ticket_status(1).outcome == "error"


def test_lookup_times_out(monkeypatch: pytest.MonkeyPatch) -> None:
    def slow(_id: int) -> TicketStatus:
        time.sleep(0.2)
        raise AssertionError("should have timed out")

    monkeypatch.setattr(incidents, "_fetch", slow)
    assert lookup_ticket_status(1, timeout_seconds=0.01).outcome == "timeout"


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("what is the return policy?", RouteDecision("rag", None)),
        ("status of ticket 42?", RouteDecision("ticket", 42)),
        ("can you check incident #7", RouteDecision("ticket", 7)),
    ],
)
def test_routing_heuristic_without_key(question: str, expected: RouteDecision) -> None:
    assert route_question(question, _config()) == expected
