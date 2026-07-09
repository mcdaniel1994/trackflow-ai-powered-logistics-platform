"""Engagement 6: Identity-owned safe auth audit logs (Phase 1 is logs only).

These assert the presence of who/what/when/outcome audit lines and the absence of any
secret material — no email, password, or token. Login auditing is not a telemetry_events
row and carries no warehouse (Identity has no warehouse claim).
"""

from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient

from conftest import create_admin, login


def test_successful_login_logs_safe_audit_line(client: TestClient, caplog: pytest.LogCaptureFixture):
    admin = create_admin(client, email="Ana@TrackFlow.test", password="warehouse-passphrase")
    with caplog.at_level(logging.INFO):
        login(client, email="Ana@TrackFlow.test", password="warehouse-passphrase")

    assert "auth.login.succeeded" in caplog.text
    assert str(admin["id"]) in caplog.text  # opaque actor id, safe
    assert "Ana@TrackFlow.test" not in caplog.text
    assert "warehouse-passphrase" not in caplog.text
    assert "warehouse" not in caplog.text.lower()  # no warehouse segmentation for auth


def test_failed_login_logs_generic_reason_without_secrets(client: TestClient, caplog: pytest.LogCaptureFixture):
    create_admin(client, email="Ana@TrackFlow.test", password="warehouse-passphrase")
    with caplog.at_level(logging.INFO):
        wrong = client.post("/auth/login", json={"email": "Ana@TrackFlow.test", "password": "nope-wrong-secret"})
        missing = client.post("/auth/login", json={"email": "ghost@example.test", "password": "nope-wrong-secret"})

    assert wrong.status_code == 401
    assert missing.status_code == 401
    assert "auth.login.failed reason=invalid_credentials" in caplog.text
    # Never leak the submitted email or password, and never reveal which accounts exist.
    assert "Ana@TrackFlow.test" not in caplog.text
    assert "ghost@example.test" not in caplog.text
    assert "nope-wrong-secret" not in caplog.text
