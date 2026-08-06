"""MCP ticket adapter and no-key routing tests; all HTTP and MCP calls are mocked."""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from central_api.domains.agents import mcp_client
from central_api.domains.agents.config import AgentConfig
from central_api.domains.agents.routing import RouteDecision, route_question


class _RagCfg:
    min_score = 0.5
    openai_api_key = ""
    generation_model = "deepseek-chat"


class _RagWithKey(_RagCfg):
    openai_api_key = "mocked-key"


def _config() -> AgentConfig:
    return AgentConfig(
        agent_name="a",
        rag=_RagCfg(),
        min_score=0.5,
        agent_model="gpt-4o-mini",
        route_timeout_seconds=8.0,
        ticket_timeout_seconds=5.0,
        mcp_url="http://mcp.test/mcp",
        mcp_resource_url="https://mcp.trackflow.test/mcp",
        oauth_token_url="http://identity.test/oauth/token",
        mcp_oauth_client_id="client-id",
        mcp_oauth_client_secret="client-secret",
        source_access_token="source-token",
    )


class _Tool:
    name = "ticket_check_status"

    def __init__(self, result: object) -> None:
        self.result = result

    async def ainvoke(self, arguments: dict[str, object]) -> object:
        assert arguments == {"ticket_id": 42}
        return self.result


class _MCPClient:
    result: object = {
        "ticket_id": 42,
        "status": "resolved",
        "category": "lost_parcel",
        "created_at": "2026-07-01T00:00:00+00:00",
        "updated_at": "2026-07-05T00:00:00+00:00",
    }

    def __init__(self, connections: dict[str, Any], **_: object) -> None:
        headers = connections["trackflow"]["headers"]
        assert headers == {"Authorization": "Bearer delegated-token"}

    async def get_tools(self, *, server_name: str) -> list[_Tool]:
        assert server_name == "trackflow"
        return [_Tool(self.result)]


@pytest.fixture
def mocked_exchange(monkeypatch: pytest.MonkeyPatch) -> None:
    async def exchange(_: mcp_client.MCPIncidentClient) -> str:
        return "delegated-token"

    monkeypatch.setattr(mcp_client.MCPIncidentClient, "_exchange_token", exchange)
    monkeypatch.setattr(mcp_client, "MultiServerMCPClient", _MCPClient)


def test_lookup_ok(mocked_exchange: None) -> None:
    result = mcp_client.lookup_ticket_status(42, _config())
    assert result.outcome == "ok"
    assert result.ticket is not None and result.ticket.status == "resolved"


def test_lookup_not_found(mocked_exchange: None) -> None:
    _MCPClient.result = [{"type": "text", "text": '{"error":"NOT_FOUND"}'}]
    try:
        assert mcp_client.lookup_ticket_status(42, _config()).outcome == "not_found"
    finally:
        _MCPClient.result = {
            "ticket_id": 42,
            "status": "resolved",
            "category": "lost_parcel",
            "created_at": "2026-07-01T00:00:00+00:00",
            "updated_at": "2026-07-05T00:00:00+00:00",
        }


def test_lookup_timeout_is_honest(monkeypatch: pytest.MonkeyPatch) -> None:
    async def timeout(_: mcp_client.MCPIncidentClient) -> str:
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(mcp_client.MCPIncidentClient, "_exchange_token", timeout)
    assert mcp_client.lookup_ticket_status(42, _config()).outcome == "timeout"


def test_client_repr_excludes_credentials() -> None:
    value = repr(mcp_client.MCPIncidentClient(_config(), "source-token"))
    assert "source-token" not in value
    assert "client-secret" not in value


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


def test_routing_provider_failure_keeps_request_available(monkeypatch: pytest.MonkeyPatch) -> None:
    class FailingChatOpenAI:
        def __init__(self, **_kwargs: object) -> None:
            raise RuntimeError("provider payload must not escape")

    base = _config()
    configured = AgentConfig(
        agent_name=base.agent_name,
        rag=_RagWithKey(),
        min_score=base.min_score,
        agent_model=base.agent_model,
        route_timeout_seconds=base.route_timeout_seconds,
        ticket_timeout_seconds=base.ticket_timeout_seconds,
        mcp_url=base.mcp_url,
        mcp_resource_url=base.mcp_resource_url,
        oauth_token_url=base.oauth_token_url,
        mcp_oauth_client_id=base.mcp_oauth_client_id,
        mcp_oauth_client_secret=base.mcp_oauth_client_secret,
        source_access_token=base.source_access_token,
    )
    monkeypatch.setattr("langchain_openai.ChatOpenAI", FailingChatOpenAI)

    assert route_question("status of ticket 42?", configured) == RouteDecision("ticket", 42)
