"""Cookie-only authentication helpers for long-lived real-time connections."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import NoReturn

from fastapi import HTTPException, Request, WebSocket, WebSocketException, status
from trackflow_auth import AuthenticatedPrincipal, verify_access_token  # type: ignore[import-untyped]

from ...core.config import Settings


@dataclass(frozen=True, slots=True)
class RealtimePrincipal:
    """Verified caller plus the access-token deadline needed by long-lived streams."""

    principal: AuthenticatedPrincipal
    expires_at: datetime


def _http_auth_error() -> NoReturn:
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def _cookie_principal(cookie_value: str | None, settings: Settings) -> RealtimePrincipal:
    if not cookie_value:
        _http_auth_error()
    claims = verify_access_token(cookie_value, settings.auth_config)
    if claims.get("status") != "active":
        _http_auth_error()
    if claims.get("must_change_password") is True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return RealtimePrincipal(
        principal=AuthenticatedPrincipal(
            user_id=str(claims["sub"]),
            role=str(claims["role"]),
            status=str(claims["status"]),
            must_change_password=bool(claims["must_change_password"]),
            token_id=str(claims["jti"]),
            token_source="cookie",
            jurisdiction=claims.get("jurisdiction") if claims.get("jurisdiction") in {"US", "ES"} else None,
        ),
        expires_at=datetime.fromtimestamp(float(claims["exp"]), tz=UTC),
    )


def authenticate_http_stream(request: Request, settings: Settings) -> RealtimePrincipal:
    """Authenticate an HTTP stream from the host-only access cookie, never a bearer header."""
    return _cookie_principal(request.cookies.get(settings.auth_config.access_cookie_name), settings)


def origin_is_allowed(origin: str | None, settings: Settings) -> bool:
    """Require an exact configured origin for cookie-authenticated WebSocket upgrades."""
    return origin is not None and origin in settings.cors_origins


def _websocket_rejected() -> NoReturn:
    raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Connection rejected")


def authenticate_websocket_upgrade(websocket: WebSocket, settings: Settings) -> RealtimePrincipal:
    """Verify exact Origin and cookie JWT before a WebSocket is accepted."""
    if not origin_is_allowed(websocket.headers.get("origin"), settings):
        _websocket_rejected()
    try:
        return _cookie_principal(websocket.cookies.get(settings.auth_config.access_cookie_name), settings)
    except HTTPException as exc:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Connection rejected",
        ) from exc
