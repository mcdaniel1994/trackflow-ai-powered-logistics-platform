"""Constants for the TrackFlow identity service."""

from __future__ import annotations

from trackflow_auth import ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME, CSRF_HEADER_NAME, REFRESH_COOKIE_NAME

ROLE_ADMIN = "admin"
ROLE_USER = "user"
VALID_ROLES = {ROLE_ADMIN, ROLE_USER}

STATUS_ACTIVE = "active"
STATUS_SUSPENDED = "suspended"
STATUS_DISABLED = "disabled"
VALID_STATUSES = {STATUS_ACTIVE, STATUS_SUSPENDED, STATUS_DISABLED}

TOKEN_TYPE_ACCESS = "access"
