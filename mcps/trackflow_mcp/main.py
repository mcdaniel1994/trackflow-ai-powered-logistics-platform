"""OAuth-protected Streamable HTTP MCP application and TrackFlow tools."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any, Literal, Protocol, TypeVar

from fastmcp import FastMCP
from mcpauth import AuthInfo
from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from .auth import build_auth, build_token_verifier
from .config import MCPSettings, get_settings
from .errors import ErrorCode, ToolFailure
from .upstream import CentralAPIClient

LOGGER = logging.getLogger(__name__)
T = TypeVar("T")

Category = Literal[
    "lost_parcel",
    "delivery_failure",
    "inventory_discrepancy",
    "carrier_issue",
    "returns_issue",
    "warehouse_incident",
    "system_failure",
    "client_complaint",
    "other",
]
Origin = Literal["customer", "branch", "internal"]
Branch = Literal["central", "la_warehouse", "la_office", "zaragoza_warehouse", "zaragoza_office"]
TicketStatus = Literal["open", "in_progress", "resolved", "discarded"]
InventoryAction = Literal["list", "get", "create", "update", "delete"]


class OperationsClient(Protocol):
    async def request(
        self,
        *,
        method: str,
        path: str,
        subject_token: str,
        scopes: frozenset[str],
        json: dict[str, object] | None = None,
        params: dict[str, str | int | float | bool | None] | None = None,
        idempotent: bool = False,
    ) -> dict[str, Any]: ...


def _ticket_summary(payload: dict[str, Any]) -> dict[str, object]:
    return {
        "ticket_id": payload.get("id"),
        "status": payload.get("status"),
        "category": payload.get("category"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
    }


async def _health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def build_app(
    settings: MCPSettings | None = None,
    *,
    upstream: OperationsClient | None = None,
) -> Starlette:
    resolved = settings or get_settings()
    auth = build_auth(resolved)
    client = upstream or CentralAPIClient(resolved)
    mcp = FastMCP(
        "TrackFlow Operations",
        instructions="Authorized tools for TrackFlow incidents and read-only inventory.",
        mask_error_details=True,
        strict_input_validation=True,
    )

    async def readiness(_: Request) -> JSONResponse:
        configured = bool(
            resolved.identity_jwt_public_key.strip()
            and resolved.oauth_client_id.strip()
            and resolved.oauth_client_secret.get_secret_value()
        )
        return JSONResponse({"status": "ok" if configured else "not_ready"}, status_code=200 if configured else 503)

    def principal(required_scope: str) -> AuthInfo:
        info = auth.auth_info
        if info is None:
            raise ToolFailure(ErrorCode.AUTHENTICATION_REQUIRED, "Authentication is required.")
        if required_scope not in info.scopes:
            raise ToolFailure(ErrorCode.INSUFFICIENT_SCOPE, "The token does not grant this operation.")
        return info

    async def invoke(
        *,
        tool: str,
        required_scope: str,
        operation: Callable[[AuthInfo], Awaitable[T]],
    ) -> T:
        started = time.perf_counter()
        info: AuthInfo | None = None
        outcome = "error"
        error_code = "NONE"
        try:
            info = principal(required_scope)
            result = await operation(info)
            outcome = "ok"
            return result
        except ToolFailure as exc:
            error_code = exc.code
            raise exc.as_tool_error() from exc
        finally:
            duration_ms = max(0, int((time.perf_counter() - started) * 1000))
            LOGGER.info(
                "mcp.tool client_id=%s subject=%s tool=%s outcome=%s error_code=%s duration_ms=%s",
                info.client_id if info else "unknown",
                info.subject if info else "unknown",
                tool,
                outcome,
                error_code,
                duration_ms,
            )

    @mcp.tool(
        name="ticket_check_status",
        description="Read the current status and safe lifecycle fields for a TrackFlow incident ticket.",
    )
    async def ticket_check_status(ticket_id: int) -> dict[str, object]:
        async def operation(info: AuthInfo) -> dict[str, object]:
            if ticket_id <= 0:
                raise ToolFailure(ErrorCode.INVALID_INPUT, "ticket_id must be a positive integer.")
            payload = await client.request(
                method="GET",
                path=f"/api/incidents/{ticket_id}",
                subject_token=info.token,
                scopes=frozenset({"incidents:read"}),
                idempotent=True,
            )
            return _ticket_summary(payload)

        return await invoke(tool="ticket_check_status", required_scope="incidents:read", operation=operation)

    @mcp.tool(
        name="ticket_create",
        description="Create a TrackFlow incident ticket. This operation is not retried automatically.",
    )
    async def ticket_create(
        title: str,
        description: str,
        category: Category,
        origin: Origin,
        branch: Branch,
    ) -> dict[str, object]:
        async def operation(info: AuthInfo) -> dict[str, object]:
            if not title.strip() or len(title) > 200 or len(description.strip()) < 5 or len(description) > 5000:
                raise ToolFailure(ErrorCode.INVALID_INPUT, "Ticket title or description is invalid.")
            payload = await client.request(
                method="POST",
                path="/api/incidents",
                subject_token=info.token,
                scopes=frozenset({"incidents:write"}),
                json={
                    "title": title,
                    "description": description,
                    "category": category,
                    "origin": origin,
                    "branch": branch,
                },
            )
            return _ticket_summary(payload)

        return await invoke(tool="ticket_create", required_scope="incidents:write", operation=operation)

    @mcp.tool(
        name="ticket_update_status",
        description="Move a TrackFlow incident to an allowed lifecycle status. This operation is not retried.",
    )
    async def ticket_update_status(ticket_id: int, status: TicketStatus) -> dict[str, object]:
        async def operation(info: AuthInfo) -> dict[str, object]:
            if ticket_id <= 0:
                raise ToolFailure(ErrorCode.INVALID_INPUT, "ticket_id must be a positive integer.")
            payload = await client.request(
                method="PATCH",
                path=f"/api/incidents/{ticket_id}/status",
                subject_token=info.token,
                scopes=frozenset({"incidents:write"}),
                json={"status": status},
            )
            return _ticket_summary(payload)

        return await invoke(tool="ticket_update_status", required_scope="incidents:write", operation=operation)

    @mcp.tool(
        name="inventory_access",
        description=(
            "Read TrackFlow products with action=list or action=get. Mutating actions are intentionally denied."
        ),
    )
    async def inventory_access(
        action: InventoryAction,
        sku_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        async def operation(info: AuthInfo) -> dict[str, Any]:
            if action in {"create", "update", "delete"}:
                raise ToolFailure(
                    ErrorCode.INVENTORY_READ_ONLY,
                    "Inventory tools are read-only; no upstream request was made.",
                )
            if limit < 1 or limit > 100 or offset < 0 or (action == "get" and (sku_id is None or sku_id <= 0)):
                raise ToolFailure(ErrorCode.INVALID_INPUT, "Inventory query arguments are invalid.")
            if action == "get":
                path = f"/inventory/products/{sku_id}"
                params: dict[str, str | int | float | bool | None] | None = None
            else:
                path = "/inventory/products"
                params = {"limit": limit, "offset": offset}
            return await client.request(
                method="GET",
                path=path,
                subject_token=info.token,
                scopes=frozenset({"inventory:read"}),
                params=params,
                idempotent=True,
            )

        return await invoke(tool="inventory_access", required_scope="inventory:read", operation=operation)

    bearer_middleware = auth.bearer_auth_middleware(
        build_token_verifier(resolved),
        audience=resolved.mcp_resource_url,
        required_scopes=["mcp:connect"],
        show_error_details=False,
        resource=resolved.mcp_resource_url,
    )
    transport = mcp.http_app(
        path="/",
        middleware=[Middleware(bearer_middleware)],
        transport="streamable-http",
        stateless_http=True,
        json_response=True,
    )
    routes = [
        Route("/health/live", _health, methods=["GET"]),
        Route("/health/ready", readiness, methods=["GET"]),
        *auth.resource_metadata_router().routes,
        Mount("/mcp", app=transport),
    ]
    return Starlette(routes=routes, lifespan=transport.lifespan)


app = build_app()
