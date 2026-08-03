from __future__ import annotations

import httpx
import pytest
from pydantic import SecretStr

from trackflow_mcp.config import MCPSettings
from trackflow_mcp.errors import ErrorCode, ToolFailure
from trackflow_mcp.upstream import CentralAPIClient


def _settings() -> MCPSettings:
    return MCPSettings(
        identity_oauth_issuer_url="https://identity.trackflow.test",
        identity_oauth_internal_url="https://identity-internal.trackflow.test",
        mcp_resource_url="https://mcp.trackflow.test/mcp",
        central_api_url="https://api-internal.trackflow.test",
        central_api_oauth_resource_url="https://api.trackflow.test",
        oauth_client_id="mcp-client",
        oauth_client_secret=SecretStr("secret"),
    )


def _response(status: int, payload: object) -> httpx.Response:
    return httpx.Response(status, json=payload, request=httpx.Request("GET", "https://test"))


class FakeHTTPClient:
    token_response = _response(200, {"access_token": "central-token"})
    outcomes: list[object] = [_response(200, {"id": 1})]
    posts: list[dict[str, object]] = []
    requests: list[dict[str, object]] = []

    def __init__(self, **_: object) -> None:
        pass

    async def __aenter__(self) -> FakeHTTPClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def post(self, url: str, **kwargs: object) -> httpx.Response:
        self.posts.append({"url": url, **kwargs})
        return self.token_response

    async def request(self, method: str, url: str, **kwargs: object) -> httpx.Response:
        self.requests.append({"method": method, "url": url, **kwargs})
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        assert isinstance(outcome, httpx.Response)
        return outcome


@pytest.fixture(autouse=True)
def reset_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    FakeHTTPClient.token_response = _response(200, {"access_token": "central-token"})
    FakeHTTPClient.outcomes = [_response(200, {"id": 1})]
    FakeHTTPClient.posts = []
    FakeHTTPClient.requests = []
    monkeypatch.setattr("trackflow_mcp.upstream.httpx.AsyncClient", FakeHTTPClient)


@pytest.mark.asyncio
async def test_delegated_exchange_and_idempotent_read_retry() -> None:
    FakeHTTPClient.outcomes = [_response(503, {}), _response(200, {"id": 9})]
    payload = await CentralAPIClient(_settings()).request(
        method="GET",
        path="/api/incidents/9",
        subject_token="mcp-token",
        scopes=frozenset({"incidents:read"}),
        idempotent=True,
    )
    assert payload == {"id": 9}
    assert len(FakeHTTPClient.requests) == 2
    exchange = FakeHTTPClient.posts[0]
    assert exchange["url"] == "https://identity-internal.trackflow.test/oauth/token"
    data = exchange["data"]
    assert isinstance(data, dict)
    assert data["resource"] == "https://api.trackflow.test"
    assert data["scope"] == "incidents:read"


@pytest.mark.asyncio
async def test_write_is_never_retried() -> None:
    FakeHTTPClient.outcomes = [_response(503, {}), _response(200, {"id": 1})]
    with pytest.raises(ToolFailure) as exc_info:
        await CentralAPIClient(_settings()).request(
            method="POST",
            path="/api/incidents",
            subject_token="mcp-token",
            scopes=frozenset({"incidents:write"}),
        )
    assert exc_info.value.code == ErrorCode.UPSTREAM_UNAVAILABLE
    assert len(FakeHTTPClient.requests) == 1


@pytest.mark.asyncio
async def test_idempotent_connect_failure_retries_once() -> None:
    request = httpx.Request("GET", "https://test")
    FakeHTTPClient.outcomes = [httpx.ConnectError("down", request=request), _response(200, {"id": 2})]
    result = await CentralAPIClient(_settings()).request(
        method="GET",
        path="/inventory/products/2",
        subject_token="mcp-token",
        scopes=frozenset({"inventory:read"}),
        idempotent=True,
    )
    assert result == {"id": 2}


@pytest.mark.asyncio
async def test_timeout_has_distinct_error() -> None:
    request = httpx.Request("GET", "https://test")
    FakeHTTPClient.outcomes = [httpx.ReadTimeout("slow", request=request)]
    with pytest.raises(ToolFailure) as exc_info:
        await CentralAPIClient(_settings()).request(
            method="GET",
            path="/inventory/products",
            subject_token="mcp-token",
            scopes=frozenset({"inventory:read"}),
        )
    assert exc_info.value.code == ErrorCode.UPSTREAM_TIMEOUT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "code"),
    [
        (404, ErrorCode.NOT_FOUND),
        (409, ErrorCode.INVALID_TRANSITION),
        (422, ErrorCode.INVALID_INPUT),
        (403, ErrorCode.INSUFFICIENT_SCOPE),
        (500, ErrorCode.UPSTREAM_UNAVAILABLE),
    ],
)
async def test_upstream_statuses_have_distinct_errors(status: int, code: ErrorCode) -> None:
    FakeHTTPClient.outcomes = [_response(status, {})]
    with pytest.raises(ToolFailure) as exc_info:
        await CentralAPIClient(_settings()).request(
            method="GET",
            path="/api/incidents/1",
            subject_token="mcp-token",
            scopes=frozenset({"incidents:read"}),
        )
    assert exc_info.value.code == code


@pytest.mark.asyncio
async def test_token_exchange_rejections_are_safe() -> None:
    FakeHTTPClient.token_response = _response(401, {"error": "invalid_client"})
    with pytest.raises(ToolFailure) as exc_info:
        await CentralAPIClient(_settings()).request(
            method="GET",
            path="/api/incidents/1",
            subject_token="mcp-token",
            scopes=frozenset({"incidents:read"}),
        )
    assert exc_info.value.code == ErrorCode.AUTHENTICATION_REQUIRED


@pytest.mark.asyncio
async def test_invalid_success_payload_is_unavailable() -> None:
    FakeHTTPClient.outcomes = [_response(200, ["unexpected"])]
    with pytest.raises(ToolFailure) as exc_info:
        await CentralAPIClient(_settings()).request(
            method="GET",
            path="/api/incidents/1",
            subject_token="mcp-token",
            scopes=frozenset({"incidents:read"}),
        )
    assert exc_info.value.code == ErrorCode.UPSTREAM_UNAVAILABLE


def test_production_config_requires_credentials_and_https() -> None:
    with pytest.raises(ValueError):
        MCPSettings(app_environment="production")
    with pytest.raises(ValueError):
        MCPSettings(identity_oauth_issuer_url="http://identity.example.com")
