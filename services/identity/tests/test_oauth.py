from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from jose import jwt

from identity.oauth import ACCESS_TOKEN_TYPE, TOKEN_EXCHANGE_GRANT
from identity.models import UserCreate
from identity.security import oauth_key_id

from conftest import create_admin

MCP_RESOURCE = "https://mcp.trackflow.test/mcp"
CENTRAL_RESOURCE = "https://api.trackflow.test"
REDIRECT_URI = "https://playground.test/oauth/callback"


def _challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _register_public(client: TestClient) -> str:
    response = client.post(
        "/oauth/register",
        json={
            "client_name": "MCP Playground",
            "redirect_uris": [REDIRECT_URI],
            "scope": "mcp:connect incidents:read inventory:read",
            "resource": [MCP_RESOURCE],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["client_id"])


def _authorize(
    client: TestClient, client_id: str, *, decision: str = "approve", verifier: str
) -> object:
    values = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "mcp:connect incidents:read",
        "resource": MCP_RESOURCE,
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256",
        "state": "opaque-state",
        "email": "admin@trackflow.test",
        "password": "admin-passphrase",
        "decision": decision,
    }
    return client.post("/oauth/authorize", data=values, follow_redirects=False)


def _code(response: object) -> str:
    location = response.headers["location"]  # type: ignore[attr-defined]
    query = parse_qs(urlparse(location).query)
    assert query["state"] == ["opaque-state"]
    return query["code"][0]


def test_metadata_jwks_and_accessible_consent(client: TestClient) -> None:
    client_id = _register_public(client)
    verifier = "a" * 64
    response = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "mcp:connect incidents:read",
            "resource": MCP_RESOURCE,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            "state": "opaque-state",
        },
    )
    assert response.status_code == 200
    assert '<label for="email">Email</label>' in response.text
    assert (
        '<button type="submit" name="decision" value="deny">Deny</button>'
        in response.text
    )
    assert "opaque-state" in response.text

    metadata = client.get("/.well-known/oauth-authorization-server").json()
    assert metadata["issuer"] == "http://localhost:8002"
    assert metadata["code_challenge_methods_supported"] == ["S256"]
    assert "refresh_token" not in metadata["grant_types_supported"]
    jwks = client.get("/oauth/jwks.json").json()
    assert jwks["keys"][0]["alg"] == "RS256"
    assert jwks["keys"][0]["kid"] == oauth_key_id(client.app.state.identity_settings)


def test_pkce_code_is_five_minute_hash_only_single_use_and_preserves_state(
    client: TestClient,
    key_pair: tuple[str, str],
) -> None:
    create_admin(client)
    client_id = _register_public(client)
    verifier = "v" * 64
    authorized = _authorize(client, client_id, verifier=verifier)
    assert authorized.status_code == 303
    code = _code(authorized)

    records = client.app.state.identity_store.db.table(
        "oauth_authorization_codes"
    ).all()
    assert len(records) == 1
    assert code not in str(records[0])
    expiry = datetime.fromisoformat(str(records[0]["expires_at"]))
    assert (
        timedelta(minutes=4, seconds=50)
        <= expiry - datetime.now(UTC)
        <= timedelta(minutes=5)
    )

    token = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    assert token.status_code == 200, token.text
    assert token.json()["expires_in"] == 900
    header = jwt.get_unverified_header(token.json()["access_token"])
    claims = jwt.decode(
        token.json()["access_token"],
        key_pair[1],
        algorithms=["RS256"],
        issuer="http://localhost:8002",
        audience=MCP_RESOURCE,
    )
    assert header["kid"] == oauth_key_id(client.app.state.identity_settings)
    assert claims["scope"] == "incidents:read mcp:connect"
    assert claims["jurisdiction"] == "US"

    reused = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    assert reused.status_code == 400 and reused.json()["error"] == "invalid_grant"


def test_pkce_redirect_denial_and_expired_code_fail_closed(client: TestClient) -> None:
    create_admin(client)
    client_id = _register_public(client)
    verifier = "p" * 64

    bad_redirect = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": f"{REDIRECT_URI}/attacker",
            "response_type": "code",
            "scope": "mcp:connect",
            "resource": MCP_RESOURCE,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
        },
    )
    assert bad_redirect.status_code == 400

    invalid_scope = client.get(
        "/oauth/authorize",
        params={
            "client_id": client_id,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": "incidents:write",
            "resource": MCP_RESOURCE,
            "code_challenge": _challenge(verifier),
            "code_challenge_method": "S256",
            "state": "opaque-state",
        },
        follow_redirects=False,
    )
    assert invalid_scope.status_code == 303
    invalid_scope_query = parse_qs(urlparse(invalid_scope.headers["location"]).query)
    assert invalid_scope_query["error"] == ["invalid_scope"]
    assert invalid_scope_query["state"] == ["opaque-state"]

    denied = _authorize(client, client_id, decision="deny", verifier=verifier)
    assert denied.status_code == 303
    denied_query = parse_qs(urlparse(denied.headers["location"]).query)
    assert denied_query == {
        "error": ["access_denied"],
        "error_description": ["The resource owner denied the request."],
        "state": ["opaque-state"],
    }

    code = _code(_authorize(client, client_id, verifier=verifier))
    table = client.app.state.identity_store.db.table("oauth_authorization_codes")
    table.update({"expires_at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat()})
    expired = client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": verifier,
        },
    )
    assert expired.status_code == 400 and expired.json()["error"] == "invalid_grant"


def test_wrong_pkce_verifier_burns_the_authorization_code(client: TestClient) -> None:
    create_admin(client)
    client_id = _register_public(client)
    verifier = "q" * 64
    code = _code(_authorize(client, client_id, verifier=verifier))
    token_request = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }

    rejected = client.post(
        "/oauth/token", data={**token_request, "code_verifier": "w" * 64}
    )
    assert rejected.status_code == 400 and rejected.json()["error"] == "invalid_grant"

    burned = client.post(
        "/oauth/token", data={**token_request, "code_verifier": verifier}
    )
    assert burned.status_code == 400 and burned.json()["error"] == "invalid_grant"


def test_confidential_machine_and_delegated_exchange_downscope(
    client: TestClient,
    key_pair: tuple[str, str],
) -> None:
    admin = create_admin(client)
    login = client.post(
        "/auth/login", json={"email": admin["email"], "password": "admin-passphrase"}
    )
    backoffice_token = login.cookies["trackflow_access"]
    service = client.app.state.oauth_service
    central_id, central_secret = service.register_confidential_client(
        client_name="Central agent",
        grants=frozenset({TOKEN_EXCHANGE_GRANT}),
        scopes=frozenset({"mcp:connect", "incidents:read"}),
        resources=[MCP_RESOURCE],
        source_audiences=["trackflow-backoffice"],
    )
    mcp_id, mcp_secret = service.register_confidential_client(
        client_name="MCP",
        grants=frozenset({"client_credentials", TOKEN_EXCHANGE_GRANT}),
        scopes=frozenset({"incidents:read", "inventory:read"}),
        resources=[CENTRAL_RESOURCE],
        source_audiences=[MCP_RESOURCE],
    )
    stored_clients = client.app.state.identity_store.db.table("oauth_clients").all()
    assert central_secret not in str(stored_clients)
    assert mcp_secret not in str(stored_clients)

    delegated = client.post(
        "/oauth/token",
        auth=(central_id, central_secret),
        data={
            "grant_type": TOKEN_EXCHANGE_GRANT,
            "subject_token": backoffice_token,
            "subject_token_type": ACCESS_TOKEN_TYPE,
            "scope": "mcp:connect incidents:read",
            "resource": MCP_RESOURCE,
        },
    )
    assert delegated.status_code == 200, delegated.text
    central = client.post(
        "/oauth/token",
        auth=(mcp_id, mcp_secret),
        data={
            "grant_type": TOKEN_EXCHANGE_GRANT,
            "subject_token": delegated.json()["access_token"],
            "subject_token_type": ACCESS_TOKEN_TYPE,
            "scope": "incidents:read",
            "resource": CENTRAL_RESOURCE,
        },
    )
    assert central.status_code == 200, central.text
    claims = jwt.decode(
        central.json()["access_token"],
        key_pair[1],
        algorithms=["RS256"],
        issuer="http://localhost:8002",
        audience=CENTRAL_RESOURCE,
    )
    assert claims["sub"] == admin["id"]
    assert claims["client_id"] == mcp_id
    assert claims["scope"] == "incidents:read"
    assert claims["jurisdiction"] == "US"

    increased = client.post(
        "/oauth/token",
        auth=(mcp_id, mcp_secret),
        data={
            "grant_type": TOKEN_EXCHANGE_GRANT,
            "subject_token": delegated.json()["access_token"],
            "subject_token_type": ACCESS_TOKEN_TYPE,
            "scope": "inventory:read",
            "resource": CENTRAL_RESOURCE,
        },
    )
    assert increased.status_code == 400 and increased.json()["error"] == "invalid_scope"

    machine = client.post(
        "/oauth/token",
        auth=(mcp_id, mcp_secret),
        data={
            "grant_type": "client_credentials",
            "scope": "inventory:read",
            "resource": CENTRAL_RESOURCE,
        },
    )
    assert machine.status_code == 200


def test_oauth_logs_exclude_credentials_and_payloads(
    client: TestClient, caplog
) -> None:
    caplog.set_level("INFO")
    create_admin(client)
    client_id = _register_public(client)
    verifier = "s" * 64
    secret_email = "admin@trackflow.test"
    secret_password = "admin-passphrase"
    _authorize(client, client_id, verifier=verifier)
    output = caplog.text
    assert client_id in output
    assert secret_email not in output
    assert secret_password not in output
    assert verifier not in output
    assert "timestamp=" in output

    injected = "secret-payload-with-newline\\nforged-event"
    client.post(
        "/oauth/token",
        data={"grant_type": injected, "client_id": injected, "client_secret": injected},
    )
    assert injected not in caplog.text


def test_inactive_and_temporary_password_users_cannot_authorize(
    client: TestClient,
) -> None:
    admin = create_admin(client)
    client_id = _register_public(client)
    verifier = "z" * 64
    client.app.state.user_service.set_status(admin["id"], "suspended")
    assert _authorize(client, client_id, verifier=verifier).status_code == 401

    temporary = client.app.state.user_service.create_user_with_temp_password(
        UserCreate(
            name="Temporary User", email="temporary@trackflow.test", jurisdiction="ES"
        )
    )
    values = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "mcp:connect incidents:read",
        "resource": MCP_RESOURCE,
        "code_challenge": _challenge(verifier),
        "code_challenge_method": "S256",
        "state": "opaque-state",
        "email": temporary.email,
        "password": temporary.temporary_password,
        "decision": "approve",
    }
    response = client.post("/oauth/authorize", data=values, follow_redirects=False)
    assert response.status_code == 401
