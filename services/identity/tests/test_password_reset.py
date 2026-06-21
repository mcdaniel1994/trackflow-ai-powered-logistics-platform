from __future__ import annotations

from datetime import timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from tinydb import Query

from identity.email import EmailDeliveryError
from identity.security import hash_password_reset_token, now_utc
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


class FailingEmailSender:
    def send_password_reset(self, *, to_email: str, reset_link: str, expires_minutes: int) -> None:
        raise EmailDeliveryError("simulated provider failure")

    def send_account_setup(self, *, to_email: str, setup_link: str, expires_minutes: int) -> None:
        raise EmailDeliveryError("simulated provider failure")


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


def test_forgot_password_is_non_enumerating_and_stores_only_token_hash(client: TestClient):
    admin = create_admin(client)
    sender = _use_email_sender(client, RecordingEmailSender())

    registered = client.post("/auth/forgot-password", json={"email": admin["email"]})
    missing = client.post("/auth/forgot-password", json={"email": "missing@example.com"})

    expected = {"message": "If that address is registered, you'll receive a link shortly."}
    assert registered.status_code == 200
    assert missing.status_code == 200
    assert registered.json() == missing.json() == expected
    assert len(sender.messages) == 1
    assert sender.messages[0]["to_email"] == admin["email"]
    assert sender.messages[0]["expires_minutes"] == 30

    token = _latest_token(sender)
    records = _reset_table(client).all()
    assert len(records) == 1
    assert records[0]["user_id"] == admin["id"]
    assert records[0]["purpose"] == "password_reset"
    assert records[0]["token_hash"] == hash_password_reset_token(token)
    assert token not in str(records[0])


def test_forgot_password_does_not_email_inactive_users(client: TestClient):
    admin = create_admin(client)
    client.app.state.user_service.repository.update_user(admin["id"], {"status": "suspended"})
    sender = _use_email_sender(client, RecordingEmailSender())

    response = client.post("/auth/forgot-password", json={"email": admin["email"]})

    assert response.status_code == 200
    assert response.json() == {"message": "If that address is registered, you'll receive a link shortly."}
    assert sender.messages == []
    assert _reset_table(client).all() == []


def test_forgot_password_email_failure_keeps_public_response_and_safe_logs(client: TestClient, caplog: pytest.LogCaptureFixture):
    admin = create_admin(client)
    _use_email_sender(client, FailingEmailSender())

    response = client.post("/auth/forgot-password", json={"email": admin["email"]})

    assert response.status_code == 200
    assert response.json() == {"message": "If that address is registered, you'll receive a link shortly."}
    assert "password_reset_email_failed" in caplog.text
    assert admin["email"] not in caplog.text
    assert "reset-password" not in caplog.text
    assert "token" not in caplog.text.lower()


def test_reset_password_rejects_invalid_expired_used_and_wrong_purpose_tokens(client: TestClient):
    admin = create_admin(client)
    sender = _use_email_sender(client, RecordingEmailSender())

    assert client.post("/auth/reset-password", json={"token": "not-real", "new_password": "new-safe-passphrase"}).status_code == 400

    client.post("/auth/forgot-password", json={"email": admin["email"]})
    expired_token = _latest_token(sender)
    reset = Query()
    _reset_table(client).update(
        {"expires_at": (now_utc() - timedelta(minutes=1)).isoformat()},
        reset.token_hash == hash_password_reset_token(expired_token),
    )
    assert client.post(
        "/auth/reset-password",
        json={"token": expired_token, "new_password": "new-safe-passphrase"},
    ).status_code == 400

    client.post("/auth/forgot-password", json={"email": admin["email"]})
    wrong_purpose_token = _latest_token(sender)
    _reset_table(client).update(
        {"purpose": "access"},
        reset.token_hash == hash_password_reset_token(wrong_purpose_token),
    )
    assert client.post(
        "/auth/reset-password",
        json={"token": wrong_purpose_token, "new_password": "new-safe-passphrase"},
    ).status_code == 400

    client.post("/auth/forgot-password", json={"email": admin["email"]})
    token = _latest_token(sender)
    assert client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "new-safe-passphrase"},
    ).status_code == 200
    assert client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "another-safe-passphrase"},
    ).status_code == 400


def test_successful_reset_changes_password_and_revokes_sessions(client: TestClient):
    admin = create_admin(client)
    sender = _use_email_sender(client, RecordingEmailSender())
    login(client, admin["email"], "admin-passphrase")
    old_refresh = client.cookies.get(REFRESH_COOKIE_NAME)

    forgot = client.post("/auth/forgot-password", json={"email": admin["email"]})
    assert forgot.status_code == 200
    token = _latest_token(sender)

    reset = client.post(
        "/auth/reset-password",
        json={"token": token, "new_password": "new-safe-passphrase"},
    )
    assert reset.status_code == 200
    assert reset.json() == {"status": "ok"}

    client.cookies.set(REFRESH_COOKIE_NAME, old_refresh)
    assert client.post("/auth/refresh", headers=csrf_headers(client)).status_code == 401

    client.cookies.clear()
    assert client.post("/auth/login", json={"email": admin["email"], "password": "admin-passphrase"}).status_code == 401
    assert client.post("/auth/login", json={"email": admin["email"], "password": "new-safe-passphrase"}).status_code == 200
    assert client.get("/auth/me").json()["must_change_password"] is False


def test_new_reset_request_invalidates_previous_unused_token(client: TestClient):
    admin = create_admin(client)
    sender = _use_email_sender(client, RecordingEmailSender())

    client.post("/auth/forgot-password", json={"email": admin["email"]})
    first_token = _latest_token(sender)
    client.post("/auth/forgot-password", json={"email": admin["email"]})
    second_token = _latest_token(sender)

    assert client.post(
        "/auth/reset-password",
        json={"token": first_token, "new_password": "first-safe-passphrase"},
    ).status_code == 400
    assert client.post(
        "/auth/reset-password",
        json={"token": second_token, "new_password": "second-safe-passphrase"},
    ).status_code == 200
