"""Reusable authentication and authorization dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request, status

from trackflow_auth import TokenVerifierConfig, authenticate_request

from .config import IdentitySettings
from .constants import ROLE_ADMIN, STATUS_ACTIVE
from .service import UserService


# Adapts identity settings into the shared verifier package config.
def verifier_config(settings: IdentitySettings) -> TokenVerifierConfig:
    return TokenVerifierConfig(
        public_key=settings.jwt_public_key,
        algorithm=settings.jwt_algorithm,
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
    )


# Verifies the access token and reloads the current active user.
def get_current_user(request: Request, user_service: UserService, settings: IdentitySettings) -> dict[str, object]:
    principal = authenticate_request(
        request,
        verifier_config(settings),
        allow_password_change_required=True,
    )
    user = user_service.get_user(principal.user_id)
    if not user or user.get("status") != STATUS_ACTIVE:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


# Blocks normal protected routes until a temporary password is changed.
def require_password_current(user: dict[str, object]) -> dict[str, object]:
    if user.get("must_change_password") is True:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Password change required")
    return user


# Enforces the minimal Auth 1 admin role.
def require_admin(user: dict[str, object]) -> dict[str, object]:
    if user.get("role") != ROLE_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


# Allows profile access only for the owner or an admin.
def require_self_or_admin(user: dict[str, object], target_user_id: str) -> None:
    if user.get("role") == ROLE_ADMIN:
        return
    if str(user.get("id")) == target_user_id:
        return
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
