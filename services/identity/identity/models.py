"""Pydantic models for identity users and auth flows."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .constants import VALID_STATUSES


# Applies the repo-wide lowercase email identity rule.
def normalize_email(value: str) -> str:
    return value.strip().casefold()


# Rejects malformed emails before they reach TinyDB.
def _validate_email(value: str) -> str:
    email = normalize_email(value)
    if not email or "@" not in email or email.startswith("@") or email.endswith("@"):
        raise ValueError("A valid email is required")
    return email


# Defines the admin-only input for creating a new Back Office user.
class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    email: str

    # Ensures users cannot be created without a display name.
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required")
        return value

    # Normalizes email once at the API boundary.
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


# Limits self/admin profile edits to the approved name field.
class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str

    # Keeps profile names meaningful after whitespace trimming.
    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name is required")
        return value


# Accepts login credentials without exposing persistence fields.
class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str
    password: str = Field(min_length=1)

    # Normalizes login lookup keys before authentication.
    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        return _validate_email(value)


# Requires reauth plus a new passphrase for password rotation.
class ChangePasswordRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=256)


# Restricts admin status changes to the three approved account states.
class AdminStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: str

    # Blocks unknown status values before authorization side effects run.
    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in VALID_STATUSES:
            raise ValueError("Status must be active, suspended, or disabled")
        return value


# Shapes user responses so hashes and tokens never leave the API.
class UserPublic(BaseModel):
    id: str
    name: str
    email: str
    role: str
    status: str
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None = None


# Adds the one-time temporary password only to create-user responses.
class UserCreated(UserPublic):
    temporary_password: str


# Documents the access-token claims identity signs and services verify.
class TokenClaims(BaseModel):
    sub: str
    role: str
    status: str
    must_change_password: bool
    iss: str
    aud: str
    iat: int
    exp: int
    jti: str
    token_type: str


# Converts raw TinyDB records into the safe public user contract.
def to_public_user(record: dict[str, Any]) -> UserPublic:
    return UserPublic.model_validate(
        {
            "id": record["id"],
            "name": record["name"],
            "email": record["email"],
            "role": record["role"],
            "status": record["status"],
            "must_change_password": bool(record["must_change_password"]),
            "created_at": record["created_at"],
            "last_login_at": record.get("last_login_at"),
        }
    )
