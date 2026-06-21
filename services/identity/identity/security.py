"""Security primitives for the identity service."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import Response
from jose import jwt

from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME

from .config import IdentitySettings
from .constants import TOKEN_TYPE_ACCESS

# Configures Argon2id with the Auth 1 memory-hard parameters.
PASSWORD_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


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


# Generates the non-HttpOnly double-submit CSRF token.
def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


# Builds minimal, non-secret claims for the short-lived access JWT.
def build_access_claims(user: dict[str, object], settings: IdentitySettings) -> dict[str, object]:
    issued_at = now_utc()
    expires_at = issued_at + timedelta(minutes=settings.access_token_expire_minutes)
    return {
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


# Signs access tokens with the identity-only RS256 private key.
def sign_access_token(user: dict[str, object], settings: IdentitySettings) -> str:
    if settings.jwt_algorithm != "RS256" or not settings.jwt_private_key:
        raise RuntimeError("Identity RS256 private key is not configured.")
    return jwt.encode(build_access_claims(user, settings), settings.jwt_private_key, algorithm=settings.jwt_algorithm)


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
        response.delete_cookie(name, path="/", secure=settings.cookie_secure, samesite=settings.cookie_samesite)
