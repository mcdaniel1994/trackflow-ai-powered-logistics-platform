from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from tinydb import Query

from identity.email import EmailDeliveryError
from identity.security import hash_password_reset_token
from trackflow_auth import REFRESH_COOKIE_NAME

from conftest import create_admin, csrf_headers, login


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    def send_password_reset(self, *, to_email: str, reset_link: str, expires_minutes: int) -> None:
        self.messages.append(
            {
                "kind": "password_reset",
                "to_email": to_email,
                "reset_link": reset_link,
                "expires_minutes": expires_minutes,
            }
        )

    def send_account_setup(self, *, to_email: str, setup_link: str, expires_minutes: int) -> None:
        self.messages.append(
            {
                "kind": "account_setup",
                "to_email": to_email,
                "reset_link": setup_link,
                "expires_minutes": expires_minutes,
            }
        )


class FailingAccountSetupSender:
    def send_password_reset(self, *, to_email: str, reset_link: str, expires_minutes: int) -> None:
        raise AssertionError("password reset email should not be sent during user creation")

    def send_account_setup(self, *, to_email: str, setup_link: str, expires_minutes: int) -> None:
        raise EmailDeliveryError("simulated provider failure")


def create_normal_user(client: TestClient, email: str = "Worker@TrackFlow.test") -> dict:
    response = client.post("/users", json={"name": "Worker User", "email": email}, headers=csrf_headers(client))
    assert response.status_code == 201, response.text
    return response.json()


def _use_email_sender(client: TestClient, sender):
    client.app.state.auth_service.email_sender = sender
    return sender


def _reset_table(client: TestClient):
    return client.app.state.identity_store.db.table("password_resets")


def _latest_token(sender: RecordingEmailSender) -> str:
    reset_link = str(sender.messages[-1]["reset_link"])
    token = parse_qs(urlparse(reset_link).query)["token"][0]
    assert token
    return token


def test_admin_create_user_returns_temp_password_and_emails_setup_link(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    sender = _use_email_sender(client, RecordingEmailSender())

    created = create_normal_user(client)

    assert created["email"] == "worker@trackflow.test"
    assert created["role"] == "user"
    assert created["status"] == "active"
    assert created["must_change_password"] is True
    assert created["temporary_password"]
    assert created["setup_email_sent"] is True
    assert "hashed_password" not in created
    assert sender.messages == [
        {
            "kind": "account_setup",
            "to_email": "worker@trackflow.test",
            "reset_link": sender.messages[0]["reset_link"],
            "expires_minutes": 30,
        }
    ]

    token = _latest_token(sender)
    records = _reset_table(client).all()
    assert len(records) == 1
    assert records[0]["user_id"] == created["id"]
    assert records[0]["purpose"] == "account_setup"
    assert records[0]["token_hash"] == hash_password_reset_token(token)
    assert token not in str(records[0])

    duplicate = client.post(
        "/users",
        json={"name": "Duplicate", "email": "worker@trackflow.test"},
        headers=csrf_headers(client),
    )
    assert duplicate.status_code == 409

    reset = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "new-safe-passphrase"},
    )
    assert reset.status_code == 200
    client.cookies.clear()
    assert client.post("/auth/login", json={"email": created["email"], "password": created["temporary_password"]}).status_code == 401
    assert client.post("/auth/login", json={"email": created["email"], "password": "new-safe-passphrase"}).status_code == 200
    assert client.get("/auth/me").json()["must_change_password"] is False


def test_admin_create_user_email_failure_keeps_account_and_safe_logs(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    _use_email_sender(client, FailingAccountSetupSender())

    created = create_normal_user(client, "setup-failure@example.com")

    assert created["email"] == "setup-failure@example.com"
    assert created["temporary_password"]
    assert created["setup_email_sent"] is False
    assert "account_setup_email_failed" in caplog.text
    assert created["email"] not in caplog.text
    assert created["temporary_password"] not in caplog.text
    assert "reset-password" not in caplog.text
    assert "token" not in caplog.text.lower()


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


def test_admin_cannot_lock_out_own_account(client: TestClient):
    admin = create_admin(client)
    create_admin(client, "SecondAdmin@TrackFlow.test")
    login(client, admin["email"], "admin-passphrase")

    for next_status in ("suspended", "disabled"):
        response = client.patch(
            f"/users/{admin['id']}/status",
            json={"status": next_status},
            headers=csrf_headers(client),
        )
        assert response.status_code == 400
        assert response.json()["detail"] == "Admins cannot suspend or disable their own account"
        assert client.get(f"/users/{admin['id']}").json()["status"] == "active"
        assert client.get("/auth/me").status_code == 200

    deleted = client.delete(f"/users/{admin['id']}", headers=csrf_headers(client))
    assert deleted.status_code == 400
    assert deleted.json()["detail"] == "Admins cannot suspend or disable their own account"
    assert client.get(f"/users/{admin['id']}").json()["status"] == "active"
    assert client.get("/auth/me").status_code == 200


def test_admin_can_revoke_user_sessions_without_status_change(client: TestClient):
    admin = create_admin(client)
    login(client, admin["email"], "admin-passphrase")
    created = create_normal_user(client, "revoke@example.com")

    login(client, created["email"], created["temporary_password"])
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    login(client, admin["email"], "admin-passphrase")
    revoked = client.post(
        f"/users/{created['id']}/sessions/revoke",
        headers=csrf_headers(client),
    )
    assert revoked.status_code == 200
    assert revoked.json() == {"status": "ok"}
    assert client.get(f"/users/{created['id']}").json()["status"] == "active"

    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    assert client.post("/auth/refresh", headers=csrf_headers(client)).status_code == 401
