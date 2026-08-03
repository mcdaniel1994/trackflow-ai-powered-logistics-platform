from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, cast
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from mcp.client.streamable_http import McpHttpClientFactory
from pydantic import SecretStr
from starlette.testclient import TestClient

from trackflow_mcp.config import MCPSettings
from trackflow_mcp.main import build_app


@pytest.fixture
def key_pair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return private, public


@pytest.fixture
def settings(key_pair: tuple[str, str]) -> MCPSettings:
    return MCPSettings(
        identity_jwt_public_key=key_pair[1],
        identity_oauth_issuer_url="https://identity.trackflow.test",
        identity_oauth_internal_url="https://identity-internal.trackflow.test",
        mcp_resource_url="https://mcp.trackflow.test/mcp",
        central_api_url="https://api-internal.trackflow.test",
        central_api_oauth_resource_url="https://api.trackflow.test",
        oauth_client_id="mcp-service",
        oauth_client_secret=SecretStr("mcp-secret"),
    )


def _token(
    private_key: str,
    *,
    scopes: str = "mcp:connect incidents:read incidents:write inventory:read",
    issuer: str = "https://identity.trackflow.test",
    audience: str = "https://mcp.trackflow.test/mcp",
    expires: timedelta = timedelta(minutes=10),
) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": "11111111-1111-4111-8111-111111111111",
            "client_id": "external-client",
            "role": "user",
            "status": "active",
            "scope": scopes,
            "iss": issuer,
            "aud": audience,
            "exp": now + expires,
            "iat": now,
            "jti": str(uuid4()),
            "token_type": "access",
        },
        private_key,
        algorithm="RS256",
    )


class UpstreamStub:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

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
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "subject_token": subject_token,
                "scopes": scopes,
                "json": json,
                "params": params,
                "idempotent": idempotent,
            }
        )
        if path == "/inventory/products":
            return {"items": [], "total": 0, "limit": 50, "offset": 0}
        if path.startswith("/inventory/products/"):
            return {"id": 8, "name": "Product", "warehouse": "LA"}
        return {
            "id": 42,
            "status": "open",
            "category": "carrier_issue",
            "created_at": "2026-08-01T00:00:00Z",
            "updated_at": "2026-08-01T00:00:00Z",
        }


def test_health_and_protected_resource_metadata_are_public(settings: MCPSettings) -> None:
    app = build_app(settings, upstream=UpstreamStub())
    with TestClient(app) as client:
        assert client.get("/health/live").json() == {"status": "ok"}
        assert client.get("/health/ready").json() == {"status": "ok"}
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
    assert metadata.status_code == 200
    assert metadata.json()["resource"] == settings.mcp_resource_url
    assert metadata.json()["authorization_servers"] == [settings.identity_oauth_issuer_url]
    assert set(metadata.json()["scopes_supported"]) == {
        "mcp:connect",
        "incidents:read",
        "incidents:write",
        "inventory:read",
    }


def test_readiness_fails_closed_without_oauth_configuration() -> None:
    app = build_app(MCPSettings(), upstream=UpstreamStub())
    with TestClient(app) as client:
        assert client.get("/health/live").status_code == 200
        readiness = client.get("/health/ready")
    assert readiness.status_code == 503
    assert readiness.json() == {"status": "not_ready"}


def test_production_accepts_private_http_transports_with_public_https_identifiers(
    key_pair: tuple[str, str],
) -> None:
    configured = MCPSettings(
        app_environment="production",
        identity_oauth_issuer_url="https://identity.trackflow.test",
        identity_oauth_internal_url="http://identity:8000",
        identity_jwt_public_key=key_pair[1],
        oauth_client_id="mcp-service",
        oauth_client_secret=SecretStr("mcp-secret"),
        mcp_resource_url="https://mcp.trackflow.test/mcp",
        central_api_url="http://central-api:8000",
        central_api_oauth_resource_url="https://api.trackflow.test",
    )
    assert configured.oauth_token_url == "http://identity:8000/oauth/token"


def test_production_rejects_public_http_oauth_identifiers(key_pair: tuple[str, str]) -> None:
    with pytest.raises(ValueError, match="Public OAuth URLs"):
        MCPSettings(
            app_environment="production",
            identity_oauth_issuer_url="http://identity.example.test",
            identity_oauth_internal_url="http://identity:8000",
            identity_jwt_public_key=key_pair[1],
            oauth_client_id="mcp-service",
            oauth_client_secret=SecretStr("mcp-secret"),
            mcp_resource_url="https://mcp.trackflow.test/mcp",
            central_api_url="http://central-api:8000",
            central_api_oauth_resource_url="https://api.trackflow.test",
        )


@pytest.mark.parametrize("kind", ["missing", "signature", "issuer", "audience", "expired"])
def test_entire_transport_rejects_invalid_bearer_tokens(
    settings: MCPSettings,
    key_pair: tuple[str, str],
    kind: str,
) -> None:
    private, _ = key_pair
    headers: dict[str, str] = {}
    if kind != "missing":
        token = _token(
            private,
            issuer="https://wrong.test" if kind == "issuer" else settings.identity_oauth_issuer_url,
            audience="https://wrong.test" if kind == "audience" else settings.mcp_resource_url,
            expires=timedelta(minutes=-1) if kind == "expired" else timedelta(minutes=10),
        )
        if kind == "signature":
            other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            other_private = other_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            ).decode()
            token = _token(other_private)
        headers = {"Authorization": f"Bearer {token}"}
    with TestClient(build_app(settings, upstream=UpstreamStub())) as client:
        response = client.post("/mcp/", headers=headers, json={})
    assert response.status_code == 401


def test_missing_global_connect_scope_is_403(settings: MCPSettings, key_pair: tuple[str, str]) -> None:
    token = _token(key_pair[0], scopes="incidents:read")
    with TestClient(build_app(settings, upstream=UpstreamStub())) as client:
        response = client.post("/mcp/", headers={"Authorization": f"Bearer {token}"}, json={})
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_discovery_schemas_and_exact_upstream_routes(
    settings: MCPSettings,
    key_pair: tuple[str, str],
    caplog: pytest.LogCaptureFixture,
) -> None:
    upstream = UpstreamStub()
    app = build_app(settings, upstream=upstream)
    token = _token(key_pair[0])

    def factory(**kwargs: object) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://mcp.test",
            follow_redirects=True,
            headers=cast(dict[str, str] | None, kwargs.get("headers")),
            timeout=cast(httpx.Timeout | None, kwargs.get("timeout")),
            auth=cast(httpx.Auth | None, kwargs.get("auth")),
        )

    transport = StreamableHttpTransport(
        "http://mcp.test/mcp/",
        headers={"Authorization": f"Bearer {token}"},
        httpx_client_factory=cast(McpHttpClientFactory, factory),
    )
    async with app.router.lifespan_context(app), Client(transport) as client:
        tools = await client.list_tools()
        by_name = {tool.name: tool for tool in tools}
        assert set(by_name) == {
            "ticket_check_status",
            "ticket_create",
            "ticket_update_status",
            "inventory_access",
        }
        assert set(by_name["ticket_create"].inputSchema["properties"]) == {
            "title",
            "description",
            "category",
            "origin",
            "branch",
        }
        assert set(by_name["ticket_check_status"].inputSchema["properties"]) == {"ticket_id"}
        assert set(by_name["ticket_update_status"].inputSchema["properties"]) == {"ticket_id", "status"}
        assert set(by_name["inventory_access"].inputSchema["properties"]) == {
            "action",
            "sku_id",
            "limit",
            "offset",
        }
        assert all(tool.inputSchema.get("additionalProperties") is False for tool in by_name.values())
        checked = await client.call_tool("ticket_check_status", {"ticket_id": 42})
        created = await client.call_tool(
            "ticket_create",
            {
                "title": "Carrier delay",
                "description": "The carrier missed the promised delivery window.",
                "category": "carrier_issue",
                "origin": "branch",
                "branch": "la_office",
            },
        )
        updated = await client.call_tool("ticket_update_status", {"ticket_id": 42, "status": "in_progress"})
        listed = await client.call_tool("inventory_access", {"action": "list", "limit": 50, "offset": 0})
        rejected = await client.call_tool("inventory_access", {"action": "delete", "sku_id": 8}, raise_on_error=False)
        invalid = await client.call_tool("ticket_check_status", {"ticket_id": 0}, raise_on_error=False)

    assert checked.structured_content["ticket_id"] == 42
    assert created.structured_content["ticket_id"] == 42
    assert updated.structured_content["status"] == "open"
    assert listed.structured_content["total"] == 0
    assert rejected.is_error is True
    assert "INVENTORY_READ_ONLY" in rejected.content[0].text
    assert invalid.is_error is True
    assert "INVALID_INPUT" in invalid.content[0].text
    assert [call["path"] for call in upstream.calls] == [
        "/api/incidents/42",
        "/api/incidents",
        "/api/incidents/42/status",
        "/inventory/products",
    ]
    assert [call["method"] for call in upstream.calls] == ["GET", "POST", "PATCH", "GET"]
    assert "mcp-secret" not in caplog.text
    assert token not in caplog.text
    assert "The carrier missed" not in caplog.text


@pytest.mark.asyncio
async def test_operation_scope_is_enforced_without_upstream_call(
    settings: MCPSettings,
    key_pair: tuple[str, str],
) -> None:
    upstream = UpstreamStub()
    app = build_app(settings, upstream=upstream)
    token = _token(key_pair[0], scopes="mcp:connect incidents:read")

    def factory(**kwargs: object) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app),
            base_url="http://mcp.test",
            follow_redirects=True,
            headers=cast(dict[str, str] | None, kwargs.get("headers")),
            timeout=cast(httpx.Timeout | None, kwargs.get("timeout")),
            auth=cast(httpx.Auth | None, kwargs.get("auth")),
        )

    transport = StreamableHttpTransport(
        "http://mcp.test/mcp/",
        headers={"Authorization": f"Bearer {token}"},
        httpx_client_factory=cast(McpHttpClientFactory, factory),
    )
    async with app.router.lifespan_context(app), Client(transport) as client:
        result = await client.call_tool(
            "ticket_create",
            {
                "title": "Carrier delay",
                "description": "The carrier missed the promised delivery window.",
                "category": "carrier_issue",
                "origin": "branch",
                "branch": "la_office",
            },
            raise_on_error=False,
        )
    assert result.is_error is True
    assert "INSUFFICIENT_SCOPE" in result.content[0].text
    assert upstream.calls == []
