"""FastAPI dependencies shared across Central API domains."""

from typing import Annotated, TypeAlias, cast

from fastapi import Depends, HTTPException, Request
from trackflow_auth import (  # type: ignore[import-untyped]
    AuthenticatedPrincipal,
    ScopedPrincipal,
    authenticate_request,
    authenticate_scoped_bearer,
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


OperationalPrincipal: TypeAlias = AuthenticatedPrincipal | ScopedPrincipal


def _operational_principal(
    request: Request,
    settings: Settings,
    *,
    required_scope: str,
    write: bool,
) -> OperationalPrincipal:
    """Accept legacy Back Office auth or a least-privilege OAuth token on selected routes only."""
    try:
        principal = authenticate_request(request, settings.auth_config)
    except HTTPException as legacy_error:
        if request.cookies.get(settings.auth_config.access_cookie_name):
            raise legacy_error
        return cast(
            OperationalPrincipal,
            authenticate_scoped_bearer(
                request,
                settings.oauth_auth_config,
                required_scopes=frozenset({required_scope}),
            ),
        )
    if write and principal.token_source == "cookie":
        require_csrf(request, settings.auth_config)
    return cast(OperationalPrincipal, principal)


def incidents_read_principal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationalPrincipal:
    return _operational_principal(request, settings, required_scope="incidents:read", write=False)


def incidents_write_principal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationalPrincipal:
    return _operational_principal(request, settings, required_scope="incidents:write", write=True)


def inventory_read_principal(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> OperationalPrincipal:
    return _operational_principal(request, settings, required_scope="inventory:read", write=False)
