"""FastAPI dependencies shared across Central API domains."""

from typing import Annotated

from fastapi import Depends, Request
from trackflow_auth import (  # type: ignore[import-untyped]
    AuthenticatedPrincipal,
    authenticate_request,
    require_csrf,
)

from .config import Settings, get_settings


def current_principal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedPrincipal:
    """Verify Identity's signed claims and block inactive or temporary-password users."""
    return authenticate_request(request, settings.auth_config)


def write_principal(
    request: Request,
    principal: Annotated[AuthenticatedPrincipal, Depends(current_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthenticatedPrincipal:
    """Require double-submit CSRF only when the browser supplied an auth cookie."""
    if principal.token_source == "cookie":
        require_csrf(request, settings.auth_config)
    return principal
