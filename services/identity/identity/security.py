"""Security primitives for the identity service."""

from __future__ import annotations

import hashlib
import base64
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    load_pem_private_key,
    load_pem_public_key,
)
from fastapi import Response
from jose import jwt

from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME

from .config import IdentitySettings
from .constants import TOKEN_TYPE_ACCESS

# Configures Argon2id with the Auth 1 memory-hard parameters.
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
JWT_CONFIGURATION_MESSAGE = "Identity RS256 key configuration is invalid."


class JWTConfigurationError(RuntimeError):
    """Raised when Identity cannot safely sign and verify access tokens."""


# Rejects incomplete, malformed, non-RSA, or mismatched signing keys at startup.
def validate_jwt_signing_keys(settings: IdentitySettings) -> None:
    try:
        if settings.jwt_algorithm != "RS256":
            raise ValueError("unsupported JWT algorithm")

        private_key = load_pem_private_key(
            settings.jwt_private_key.encode("utf-8"), password=None
        )
        public_key = load_pem_public_key(settings.jwt_public_key.encode("utf-8"))

        if not isinstance(private_key, rsa.RSAPrivateKey) or not isinstance(
            public_key, rsa.RSAPublicKey
        ):
            raise ValueError("JWT keys must be RSA")
        if private_key.public_key().public_numbers() != public_key.public_numbers():
            raise ValueError("JWT key pair does not match")
    except (TypeError, ValueError, UnsupportedAlgorithm):
        # The outward startup failure stays generic so PEM contents never reach logs.
        raise JWTConfigurationError(JWT_CONFIGURATION_MESSAGE) from None


# Centralizes timezone-aware UTC timestamps for auth records.
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


# Persists timestamps as ISO strings for TinyDB portability.
def now_iso() -> str:
    return now_utc().isoformat()


# Hashes plaintext passwords with Argon2id before storage.
def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


# Verifies a submitted password without leaking mismatch details.
def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(hashed_password, password)
    except (VerifyMismatchError, VerificationError):
        return False


# Generates first-login passwords that admins can hand off once.
def generate_temporary_password() -> str:
    return secrets.token_urlsafe(24)


# Creates high-entropy opaque refresh tokens for server-side sessions.
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


# Creates high-entropy opaque reset tokens for account recovery.
def generate_password_reset_token() -> str:
    return secrets.token_urlsafe(48)


# Stores only a digest of refresh tokens in TinyDB.
def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# Stores only a digest of reset tokens in TinyDB.
def hash_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_oauth_token(token: str) -> str:
    """Hash one-time OAuth codes before persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def oauth_key_id(settings: IdentitySettings) -> str:
    """Return a stable, non-secret identifier for the configured RSA public key."""
    return hashlib.sha256(settings.jwt_public_key.encode("utf-8")).hexdigest()[:16]


def oauth_jwks(settings: IdentitySettings) -> dict[str, object]:
    """Expose the configured RS256 public key as a minimal JWKS document."""
    public_key = load_pem_public_key(settings.jwt_public_key.encode("utf-8"))
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise JWTConfigurationError(JWT_CONFIGURATION_MESSAGE)
    numbers = public_key.public_numbers()

    def encode_int(value: int) -> str:
        raw = value.to_bytes((value.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")

    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "alg": "RS256",
                "kid": oauth_key_id(settings),
                "n": encode_int(numbers.n),
                "e": encode_int(numbers.e),
            }
        ]
    }


def sign_oauth_access_token(
    *,
    subject: str,
    client_id: str,
    scopes: frozenset[str],
    audience: str,
    settings: IdentitySettings,
    role: str = "service",
    status: str = "active",
    actor: str | None = None,
    jurisdiction: str | None = None,
) -> tuple[str, int]:
    """Sign a short-lived OAuth resource token with explicit audience and scopes."""
    issued_at = now_utc()
    expires_in = settings.oauth_access_token_expire_minutes * 60
    claims: dict[str, object] = {
        "sub": subject,
        "client_id": client_id,
        "role": role,
        "status": status,
        "scope": " ".join(sorted(scopes)),
        "iss": settings.oauth_issuer_url,
        "aud": audience,
        "iat": int(issued_at.timestamp()),
        "exp": int(issued_at.timestamp()) + expires_in,
        "jti": str(uuid4()),
        "token_type": TOKEN_TYPE_ACCESS,
    }
    if actor:
        claims["act"] = {"sub": actor}
    if jurisdiction in {"US", "ES"}:
        claims["jurisdiction"] = jurisdiction
    token = jwt.encode(
        claims,
        settings.jwt_private_key,
        algorithm=settings.jwt_algorithm,
        headers={"kid": oauth_key_id(settings)},
    )
    return str(token), expires_in


# Generates the non-HttpOnly double-submit CSRF token.
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# Builds minimal, non-secret claims for the short-lived access JWT.
def build_access_claims(
    user: dict[str, object], settings: IdentitySettings
) -> dict[str, object]:
    issued_at = now_utc()
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    claims: dict[str, object] = {
        "sub": str(user["id"]),
        "role": str(user["role"]),
        "status": str(user["status"]),
        "must_change_password": bool(user["must_change_password"]),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": str(uuid4()),
        "token_type": TOKEN_TYPE_ACCESS,
    }
    if user.get("jurisdiction") in {"US", "ES"}:
        claims["jurisdiction"] = str(user["jurisdiction"])
    return claims


# Signs access tokens with the identity-only RS256 private key.
def sign_access_token(user: dict[str, object], settings: IdentitySettings) -> str:
    if settings.jwt_algorithm != "RS256" or not settings.jwt_private_key:
        raise RuntimeError("Identity RS256 private key is not configured.")
    return jwt.encode(
        build_access_claims(user, settings),
        settings.jwt_private_key,
        algorithm=settings.jwt_algorithm,
    )


# Sets access, refresh, and CSRF cookies with environment-driven flags.
def set_auth_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
    settings: IdentitySettings,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.access_token_expire_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        path="/",
    )


# Clears every Auth 1 cookie during logout.
def clear_auth_cookies(response: Response, settings: IdentitySettings) -> None:
    for name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(
            name,
            path="/",
            secure=settings.cookie_secure,
            samesite=settings.cookie_samesite,
        )
