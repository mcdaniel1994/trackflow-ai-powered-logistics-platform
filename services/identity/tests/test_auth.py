from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from jose import jwt

from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME

from conftest import create_admin, csrf_headers, login


def _signed_token(private_key: str, **overrides) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": "missing-user",
        "role": "user",
        "status": "active",
        "must_change_password": False,
        "iss": "trackflow-identity",
        "aud": "trackflow-backoffice",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "jti": "test-token",
        "token_type": "access",
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_health_login_me_and_no_register_endpoint(client: TestClient):
    admin = create_admin(client)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.post("/auth/register", json={}).status_code == 404

    response = client.post("/auth/login", json={"email": admin["email"], "password": "admin-passphrase"})
    assert response.status_code == 200
    payload = response.json()
    set_cookie = "\n".join(response.headers.get_list("set-cookie"))

    assert payload["email"] == "admin@trackflow.test"
    assert "hashed_password" not in payload
    assert f"{ACCESS_COOKIE_NAME}=" in set_cookie
    assert f"{REFRESH_COOKIE_NAME}=" in set_cookie
    assert f"{CSRF_COOKIE_NAME}=" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "SameSite=lax" in set_cookie
    assert ACCESS_COOKIE_NAME in client.cookies
    assert REFRESH_COOKIE_NAME in client.cookies
    assert CSRF_COOKIE_NAME in client.cookies

    me = client.get("/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "admin"


def test_login_failures_are_generic_and_inactive_users_cannot_login(client: TestClient):
    admin = create_admin(client)

    missing = client.post("/auth/login", json={"email": "missing@example.com", "password": "wrong"})
    wrong = client.post("/auth/login", json={"email": admin["email"], "password": "wrong"})

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json() == wrong.json() == {"detail": "Invalid email or password"}


def test_access_token_rejections(client: TestClient, key_pair):
    private_key, _public_key = key_pair
    create_admin(client)

    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401

    wrong_audience = _signed_token(private_key, aud="wrong-audience")
    expired = _signed_token(private_key, exp=int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp()))
    unknown_user = _signed_token(private_key)

    assert client.get("/auth/me", headers={"Authorization": f"Bearer {wrong_audience}"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {unknown_user}"}).status_code == 401


def test_refresh_rotation_reuse_revokes_family(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    first_refresh = client.post("/auth/refresh", headers=csrf_headers(client))
    assert first_refresh.status_code == 200
    latest_refresh = client.cookies.get(REFRESH_COOKIE_NAME)
    latest_csrf = client.cookies.get(CSRF_COOKIE_NAME)
    assert latest_refresh != old_refresh

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    client.cookies.set(CSRF_COOKIE_NAME, latest_csrf)
    reuse = client.post("/auth/refresh", headers=csrf_headers(client))
    assert reuse.status_code == 401

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE_NAME, latest_refresh)
    client.cookies.set(CSRF_COOKIE_NAME, latest_csrf)
    family_revoked = client.post("/auth/refresh", headers=csrf_headers(client))
    assert family_revoked.status_code == 401


def test_logout_revokes_refresh_session_and_clears_cookies(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    refresh_token = client.cookies.get(REFRESH_COOKIE_NAME)
    csrf_token = client.cookies.get(CSRF_COOKIE_NAME)

    logout = client.post("/auth/logout", headers=csrf_headers(client))
    assert logout.status_code == 200
    assert ACCESS_COOKIE_NAME not in client.cookies

    client.cookies.set(REFRESH_COOKIE_NAME, refresh_token)
    client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    refresh = client.post("/auth/refresh", headers=csrf_headers(client))
    assert refresh.status_code == 401
