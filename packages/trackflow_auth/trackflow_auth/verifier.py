"""RS256 access-token verification and CSRF helpers."""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, Request, status
from jose import JWTError, jwt  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict

# Names the short-lived access-token cookie shared by services.
ACCESS_COOKIE_NAME = "trackflow_access"
# Names the opaque refresh-token cookie owned by identity.
REFRESH_COOKIE_NAME = "trackflow_refresh"
# Names the non-HttpOnly CSRF cookie used for double-submit checks.
CSRF_COOKIE_NAME = "trackflow_csrf"
# Names the header that must match the CSRF cookie on writes.
CSRF_HEADER_NAME = "X-CSRF-Token"
# Limits CSRF validation to HTTP methods with side effects.
STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


# Carries the verified principal that domain services need.
class AuthenticatedPrincipal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    role: str
    status: str
    must_change_password: bool
    token_id: str
    token_source: Literal["cookie", "bearer"]
    jurisdiction: Literal["US", "ES"] | None = None


class ScopedPrincipal(BaseModel):
    """Verified OAuth bearer principal used for least-privilege service access."""

    model_config = ConfigDict(extra="forbid")

    user_id: str
    client_id: str
    role: str
    status: str
    scopes: frozenset[str]
    token_id: str
    token_source: Literal["bearer"] = "bearer"
    jurisdiction: Literal["US", "ES"] | None = None


# Carries public-key verification settings for one service.
@dataclass(frozen=True)
class TokenVerifierConfig:
    public_key: str
    issuer: str
    audience: str
    algorithm: str = "RS256"
    access_cookie_name: str = ACCESS_COOKIE_NAME
    csrf_cookie_name: str = CSRF_COOKIE_NAME
    csrf_header_name: str = CSRF_HEADER_NAME


@dataclass(frozen=True)
class OAuthTokenVerifierConfig:
    """Verification policy for one OAuth resource-server audience."""

    public_key: str
    issuer: str
    audience: str
    algorithm: str = "RS256"


# Builds the standard 401 response for failed authentication.
def _auth_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


# Builds a 403 response for authenticated but blocked callers.
def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


# Reads access tokens from cookies first, then bearer headers.
def extract_access_token(
    request: Request, cookie_name: str = ACCESS_COOKIE_NAME
) -> tuple[str, Literal["cookie", "bearer"]]:
    cookie_token = request.cookies.get(cookie_name)
    if cookie_token:
        return cookie_token, "cookie"

    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip(), "bearer"

    raise _auth_error()


# Validates RS256 signature, issuer, audience, expiry, and required claims.
def verify_access_token(token: str, config: TokenVerifierConfig) -> dict[str, Any]:
    if not config.public_key.strip():
        raise _auth_error()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _auth_error() from exc

    if header.get("alg") != config.algorithm or config.algorithm != "RS256":
        raise _auth_error()

    try:
        claims = jwt.decode(
            token,
            config.public_key,
            algorithms=[config.algorithm],
            issuer=config.issuer,
            audience=config.audience,
        )
    except JWTError as exc:
        raise _auth_error() from exc

    required = {
        "sub",
        "role",
        "status",
        "must_change_password",
        "iss",
        "aud",
        "exp",
        "iat",
        "jti",
        "token_type",
    }
    if required.difference(claims):
        raise _auth_error()
    if claims.get("token_type") != "access":
        raise _auth_error()

    return claims


# Verifies the request and enforces active/password-current claims.
def authenticate_request(
    request: Request,
    config: TokenVerifierConfig,
    *,
    allow_password_change_required: bool = False,
) -> AuthenticatedPrincipal:
    token, source = extract_access_token(request, config.access_cookie_name)
    claims = verify_access_token(token, config)

    if claims.get("status") != "active":
        raise _auth_error()
    if (
        claims.get("must_change_password") is True
        and not allow_password_change_required
    ):
        raise _forbidden("Password change required")

    return AuthenticatedPrincipal(
        user_id=str(claims["sub"]),
        role=str(claims["role"]),
        status=str(claims["status"]),
        must_change_password=bool(claims["must_change_password"]),
        token_id=str(claims["jti"]),
        token_source=source,
        jurisdiction=claims.get("jurisdiction")
        if claims.get("jurisdiction") in {"US", "ES"}
        else None,
    )


def authenticate_scoped_bearer(
    request: Request,
    config: OAuthTokenVerifierConfig,
    *,
    required_scopes: frozenset[str] = frozenset(),
) -> ScopedPrincipal:
    """Verify an OAuth bearer token and enforce the requested resource scopes.

    OAuth resource tokens are never accepted from cookies, so state-changing service calls do not
    accidentally inherit browser CSRF semantics. Issuer, audience, signature, lifetime, token type,
    and required claims are validated before scope authorization.
    """
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip() or not config.public_key.strip():
        raise _auth_error()

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise _auth_error() from exc
    if header.get("alg") != config.algorithm or config.algorithm != "RS256":
        raise _auth_error()

    try:
        claims = jwt.decode(
            token.strip(),
            config.public_key,
            algorithms=[config.algorithm],
            issuer=config.issuer,
            audience=config.audience,
        )
    except JWTError as exc:
        raise _auth_error() from exc

    required = {
        "sub",
        "client_id",
        "scope",
        "iss",
        "aud",
        "exp",
        "iat",
        "jti",
        "token_type",
    }
    if (
        required.difference(claims)
        or claims.get("token_type") != "access"
        or claims.get("status", "active") != "active"
        or not str(claims.get("sub", "")).strip()
        or not str(claims.get("client_id", "")).strip()
    ):
        raise _auth_error()

    raw_scope = claims.get("scope")
    if not isinstance(raw_scope, str):
        raise _auth_error()
    scopes = frozenset(part for part in raw_scope.split(" ") if part)
    missing = required_scopes.difference(scopes)
    if missing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient scope",
            headers={"WWW-Authenticate": 'Bearer error="insufficient_scope"'},
        )

    return ScopedPrincipal(
        user_id=str(claims["sub"]),
        client_id=str(claims["client_id"]),
        role=str(claims.get("role", "service")),
        status=str(claims.get("status", "active")),
        scopes=scopes,
        token_id=str(claims["jti"]),
        jurisdiction=claims.get("jurisdiction")
        if claims.get("jurisdiction") in {"US", "ES"}
        else None,
    )


# Enforces the double-submit CSRF cookie/header match for writes.
def require_csrf(request: Request, config: TokenVerifierConfig | None = None) -> None:
    if request.method.upper() not in STATE_CHANGING_METHODS:
        return

    csrf_cookie_name = config.csrf_cookie_name if config else CSRF_COOKIE_NAME
    csrf_header_name = config.csrf_header_name if config else CSRF_HEADER_NAME
    cookie_token = request.cookies.get(csrf_cookie_name, "")
    header_token = request.headers.get(csrf_header_name, "")

    if (
        not cookie_token
        or not header_token
        or not hmac.compare_digest(cookie_token, header_token)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
