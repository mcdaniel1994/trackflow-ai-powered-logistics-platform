from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException, Request
from jose import jwt

from trackflow_auth import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    TokenVerifierConfig,
    require_csrf,
    verify_access_token,
)


@pytest.fixture
def key_pair() -> tuple[str, str]:
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
    return private_pem, public_pem


def verifier_config(public_key: str) -> TokenVerifierConfig:
    return TokenVerifierConfig(
        public_key=public_key,
        issuer="trackflow-identity",
        audience="trackflow-backoffice",
    )


def access_claims(**overrides: Any) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    claims: dict[str, Any] = {
        "sub": "user-123",
        "role": "user",
        "status": "active",
        "must_change_password": False,
        "iss": "trackflow-identity",
        "aud": "trackflow-backoffice",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=15)).timestamp()),
        "jti": "token-123",
        "token_type": "access",
    }
    claims.update(overrides)
    return claims


def encode_token(private_key: str, claims: dict[str, Any]) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256")


def unsigned_token(claims: dict[str, Any]) -> str:
    def encode_segment(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return f"{encode_segment({'alg': 'none', 'typ': 'JWT'})}.{encode_segment(claims)}."


def request(method: str, headers: dict[str, str] | None = None) -> Request:
    header_items = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in (headers or {}).items()
    ]
    return Request({"type": "http", "method": method, "path": "/", "headers": header_items})


def assert_auth_rejected(token: str, config: TokenVerifierConfig) -> None:
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token, config)
    assert exc_info.value.status_code == 401


def test_valid_rs256_access_token_is_accepted(key_pair: tuple[str, str]):
    private_pem, public_pem = key_pair

    claims = verify_access_token(encode_token(private_pem, access_claims()), verifier_config(public_pem))

    assert claims["sub"] == "user-123"
    assert claims["token_type"] == "access"


def test_expired_token_is_rejected(key_pair: tuple[str, str]):
    private_pem, public_pem = key_pair
    expired = int((datetime.now(timezone.utc) - timedelta(minutes=1)).timestamp())

    token = encode_token(private_pem, access_claims(exp=expired))

    assert_auth_rejected(token, verifier_config(public_pem))


def test_tampered_token_is_rejected(key_pair: tuple[str, str]):
    private_pem, public_pem = key_pair
    token = encode_token(private_pem, access_claims())
    header, payload, _signature = token.split(".")

    assert_auth_rejected(f"{header}.{payload}.tampered", verifier_config(public_pem))


def test_wrong_alg_token_is_rejected(key_pair: tuple[str, str]):
    _private_pem, public_pem = key_pair
    token = jwt.encode(access_claims(), "shared-secret", algorithm="HS256")

    assert_auth_rejected(token, verifier_config(public_pem))


def test_alg_none_token_is_rejected(key_pair: tuple[str, str]):
    _private_pem, public_pem = key_pair

    assert_auth_rejected(unsigned_token(access_claims()), verifier_config(public_pem))


def test_wrong_audience_token_is_rejected(key_pair: tuple[str, str]):
    private_pem, public_pem = key_pair
    token = encode_token(private_pem, access_claims(aud="other-audience"))

    assert_auth_rejected(token, verifier_config(public_pem))


def test_missing_required_claim_is_rejected(key_pair: tuple[str, str]):
    private_pem, public_pem = key_pair
    claims = access_claims()
    del claims["jti"]

    assert_auth_rejected(encode_token(private_pem, claims), verifier_config(public_pem))


def test_non_access_token_is_rejected(key_pair: tuple[str, str]):
    private_pem, public_pem = key_pair
    token = encode_token(private_pem, access_claims(token_type="refresh"))

    assert_auth_rejected(token, verifier_config(public_pem))


def test_csrf_allows_safe_methods_without_tokens():
    require_csrf(request("GET"))


def test_csrf_allows_matching_cookie_and_header_on_state_change():
    require_csrf(
        request(
            "POST",
            {
                "Cookie": f"{CSRF_COOKIE_NAME}=csrf-token",
                CSRF_HEADER_NAME: "csrf-token",
            },
        )
    )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Cookie": f"{CSRF_COOKIE_NAME}=csrf-token"},
        {"Cookie": f"{CSRF_COOKIE_NAME}=csrf-token", CSRF_HEADER_NAME: "other-token"},
    ],
)
def test_csrf_rejects_missing_or_mismatched_state_change_tokens(headers: dict[str, str]):
    with pytest.raises(HTTPException) as exc_info:
        require_csrf(request("POST", headers))

    assert exc_info.value.status_code == 403
