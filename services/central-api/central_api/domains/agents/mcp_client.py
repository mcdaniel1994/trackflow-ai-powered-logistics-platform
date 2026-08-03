"""Typed, ephemeral client for the OAuth-protected TrackFlow MCP ticket tool."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from langchain_mcp_adapters.client import MultiServerMCPClient

from .config import AgentConfig

logger = logging.getLogger(__name__)
TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"


@dataclass(frozen=True)
class TicketStatus:
    """The safe, current ticket facts returned to graph grounding."""

    ticket_id: int
    status: str
    category: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class TicketLookupResult:
    """Typed outcome; the source and delegated bearer tokens are never included."""

    outcome: str
    ticket: TicketStatus | None
    duration_ms: int


@dataclass(repr=False)
class MCPIncidentClient:
    config: AgentConfig
    source_token: str = field(repr=False)

    async def lookup(self, ticket_id: int) -> TicketLookupResult:
        started = time.perf_counter()
        try:
            mcp_token = await self._exchange_token()
            connections: dict[str, Any] = {
                "trackflow": {
                    "transport": "streamable_http",
                    "url": self.config.mcp_url,
                    "headers": {"Authorization": f"Bearer {mcp_token}"},
                    "timeout": self.config.ticket_timeout_seconds,
                    "sse_read_timeout": self.config.ticket_timeout_seconds,
                }
            }
            tools = await MultiServerMCPClient(connections, handle_tool_errors=True).get_tools(
                server_name="trackflow"
            )
            tool = next((candidate for candidate in tools if candidate.name == "ticket_check_status"), None)
            if tool is None:
                return TicketLookupResult("error", None, self._elapsed(started))
            raw = await tool.ainvoke({"ticket_id": ticket_id})
            payload = self._payload(raw)
            error = payload.get("error")
            if error == "NOT_FOUND":
                return TicketLookupResult("not_found", None, self._elapsed(started))
            if error:
                return TicketLookupResult("error", None, self._elapsed(started))
            ticket = TicketStatus(
                ticket_id=int(payload["ticket_id"]),
                status=str(payload["status"]),
                category=str(payload["category"]),
                created_at=str(payload["created_at"]),
                updated_at=str(payload["updated_at"]),
            )
            return TicketLookupResult("ok", ticket, self._elapsed(started))
        except (TimeoutError, httpx.TimeoutException):
            logger.warning("agent_mcp_tool_failed outcome=timeout")
            return TicketLookupResult("timeout", None, self._elapsed(started))
        except Exception as exc:
            logger.warning("agent_mcp_tool_failed outcome=error error_type=%s", type(exc).__name__)
            return TicketLookupResult("error", None, self._elapsed(started))

    async def _exchange_token(self) -> str:
        timeout = httpx.Timeout(self.config.ticket_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                self.config.oauth_token_url,
                auth=(self.config.mcp_oauth_client_id, self.config.mcp_oauth_client_secret),
                data={
                    "grant_type": TOKEN_EXCHANGE_GRANT,
                    "subject_token": self.source_token,
                    "subject_token_type": ACCESS_TOKEN_TYPE,
                    "resource": self.config.mcp_resource_url,
                    "scope": "mcp:connect incidents:read",
                },
            )
        if response.status_code >= 400:
            raise RuntimeError("OAuth token exchange failed")
        payload = response.json()
        token = payload.get("access_token") if isinstance(payload, dict) else None
        if not isinstance(token, str) or not token:
            raise RuntimeError("OAuth token exchange returned no access token")
        return token

    @staticmethod
    def _payload(raw: object) -> dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str):
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        if isinstance(raw, list):
            for block in raw:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    value = json.loads(block["text"])
                    if isinstance(value, dict):
                        return value
        return {}

    @staticmethod
    def _elapsed(started: float) -> int:
        return max(0, int((time.perf_counter() - started) * 1000))


def lookup_ticket_status(ticket_id: int, config: AgentConfig) -> TicketLookupResult:
    """Run one MCP lookup from the synchronous LangGraph node."""
    return asyncio.run(MCPIncidentClient(config, config.source_access_token).lookup(ticket_id))
