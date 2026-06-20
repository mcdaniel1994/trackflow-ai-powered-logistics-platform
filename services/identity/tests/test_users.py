from __future__ import annotations

from fastapi.testclient import TestClient

from trackflow_auth import REFRESH_COOKIE_NAME

from conftest import create_admin, csrf_headers, login


def create_normal_user(client: TestClient, email: str = "Worker@TrackFlow.test") -> dict:
    response = client.post("/users", json={"name": "Worker User", "email": email}, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def test_admin_create_user_returns_temp_password_once_and_normalizes_email(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")

    created = create_normal_user(client)

    assert created["email"] == "worker@trackflow.test"
    assert created["role"] == "user"
    assert created["status"] == "active"
    assert created["must_change_password"] is True
    assert created["temporary_password"]
    assert "hashed_password" not in created

    duplicate = client.post(
        "/users",
        json={"name": "Duplicate", "email": "worker@trackflow.test"},
        headers=csrf_headers(client),
    )
    assert duplicate.status_code == 409


def test_must_change_password_lockout_and_change_password_flow(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    created = create_normal_user(client)

    login(client, created["email"], created["temporary_password"])
    assert client.get("/auth/me").json()["must_change_password"] is True
    assert client.get("/users").status_code == 403

    changed = client.post(
        "/auth/change-password",
        json={"current_password": created["temporary_password"], "new_password": "new-safe-passphrase"},
        headers=csrf_headers(client),
    )
    assert changed.status_code == 200
    assert changed.json()["must_change_password"] is False
    assert client.get(f"/users/{created['id']}").status_code == 200


def test_user_authorization_and_no_idor(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    first = create_normal_user(client, "first@example.com")
    second = create_normal_user(client, "second@example.com")

    login(client, first["email"], first["temporary_password"])
    client.post(
        "/auth/change-password",
        json={"current_password": first["temporary_password"], "new_password": "first-passphrase"},
        headers=csrf_headers(client),
    )

    assert client.get("/users").status_code == 403
    assert client.get(f"/users/{first['id']}").status_code == 200
    assert client.get(f"/users/{second['id']}").status_code == 403

    update_other = client.put(
        f"/users/{second['id']}",
        json={"name": "Not Allowed"},
        headers=csrf_headers(client),
    )
    assert update_other.status_code == 403


def test_status_suspend_and_delete_revoke_sessions(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    created = create_normal_user(client, "suspend@example.com")

    login(client, created["email"], created["temporary_password"])
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    login(client, admin["email"], "admin-passphrase")
    suspended = client.patch(
        f"/users/{created['id']}/status",
        json={"status": "suspended"},
        headers=csrf_headers(client),
    )
    assert suspended.status_code == 200
    assert suspended.json()["status"] == "suspended"

    assert client.post("/auth/login", json={"email": created["email"], "password": created["temporary_password"]}).status_code == 401
    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    assert client.post("/auth/refresh", headers=csrf_headers(client)).status_code == 401

    disabled = client.delete(f"/users/{created['id']}", headers=csrf_headers(client))
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
