from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient
from jose import jwt

from incident_processor.analysis import analyze_csv_bytes
from incident_processor.cli import main
from incident_processor.main import create_app
from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME

FIXTURE = Path(__file__).parent / "fixtures" / "sample-incidents.csv"


def test_cli_outputs_expected_metrics_without_email_leakage():
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main([str(FIXTURE)], stdin=StringIO("n\n"), stdout=stdout, stderr=stderr)
    output = stdout.getvalue()

    assert exit_code == 0
    assert stderr.getvalue() == ""
    assert "TOTAL RECORDS IN FILE .......... 100" in output
    assert "Valid records ................ 95" in output
    assert "Average score: 3.06 / 5.00" in output
    assert "@example.com" not in output


def test_cli_and_api_share_equivalent_analysis_results(monkeypatch):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    now = datetime.now(timezone.utc)
    token = jwt.encode(
        {
            "sub": "cli-api-test-user",
            "role": "user",
            "status": "active",
            "must_change_password": False,
            "iss": "trackflow-identity",
            "aud": "trackflow-backoffice",
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=15)).timestamp()),
            "jti": "cli-api-token",
            "token_type": "access",
        },
        private_pem,
        algorithm="RS256",
    )
    monkeypatch.setenv("IDENTITY_JWT_PUBLIC_KEY", public_pem)

    core_payload = analyze_csv_bytes(FIXTURE.read_bytes()).to_dict()
    client = TestClient(create_app())
    client.cookies.set(ACCESS_COOKIE_NAME, token)
    client.cookies.set(CSRF_COOKIE_NAME, "cli-api-csrf")

    with FIXTURE.open("rb") as handle:
        response = client.post(
            "/api/incidents/analyze",
            files={"file": ("sample-incidents.csv", handle, "text/csv")},
            headers={CSRF_HEADER_NAME: "cli-api-csrf"},
        )

    assert response.status_code == 200
    assert response.json() == core_payload
