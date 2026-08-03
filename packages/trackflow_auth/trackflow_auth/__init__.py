"""Shared verification helpers for TrackFlow Python services."""

from .validation import (
    safe_request_validation_exception_handler,
    safe_validation_errors,
)
from .verifier import (
    ACCESS_COOKIE_NAME,
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    REFRESH_COOKIE_NAME,
    AuthenticatedPrincipal,
    OAuthTokenVerifierConfig,
    ScopedPrincipal,
    TokenVerifierConfig,
    authenticate_request,
    authenticate_scoped_bearer,
    extract_access_token,
    require_csrf,
    verify_access_token,
)

__all__ = [
    "ACCESS_COOKIE_NAME",
    "CSRF_COOKIE_NAME",
    "CSRF_HEADER_NAME",
    "REFRESH_COOKIE_NAME",
    "AuthenticatedPrincipal",
    "OAuthTokenVerifierConfig",
    "ScopedPrincipal",
    "TokenVerifierConfig",
    "authenticate_request",
    "authenticate_scoped_bearer",
    "extract_access_token",
    "require_csrf",
    "safe_request_validation_exception_handler",
    "safe_validation_errors",
    "verify_access_token",
]
