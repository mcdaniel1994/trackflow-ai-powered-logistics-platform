"""Business services for TrackFlow identity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .config import IdentitySettings
from .constants import ROLE_ADMIN, ROLE_USER, STATUS_ACTIVE, STATUS_DISABLED, STATUS_SUSPENDED
from .models import UserCreate, UserCreated, UserPublic, UserUpdate, normalize_email, to_public_user
from .repository import DuplicateEmailError, SessionRepository, UserRepository
from .security import (
    generate_csrf_token,
    generate_refresh_token,
    generate_temporary_password,
    hash_password,
    hash_refresh_token,
    now_iso,
    sign_access_token,
    verify_password,
)


# Indicates credential or refresh-token validation failure.
class AuthenticationError(ValueError):
    """Raised when credentials or refresh sessions are invalid."""


# Reserved for route layers that need a service-level forbidden error.
class AuthorizationError(ValueError):
    """Raised when an authenticated user is forbidden."""


# Indicates a requested identity record was not found.
class NotFoundError(ValueError):
    """Raised when a requested record does not exist."""


# Bundles issued cookies and the safe user response for auth routes.
@dataclass(frozen=True)
class AuthTokens:
    access_token: str
    refresh_token: str
    csrf_token: str
    user: UserPublic


# Encapsulates admin user-management rules.
class UserService:
    # Receives the current user repository implementation.
    def __init__(self, repository: UserRepository) -> None:
        self.repository = repository

    # Creates the first trusted admin from CLI-supplied credentials.
    def create_admin(self, *, name: str, email: str, password: str) -> UserPublic:
        payload = UserCreate(name=name, email=email)
        record = self.repository.create_user(
            {
                "name": payload.name,
                "email": payload.email,
                "hashed_password": hash_password(password),
                "role": ROLE_ADMIN,
                "status": STATUS_ACTIVE,
                "must_change_password": False,
                "last_login_at": None,
            }
        )
        return to_public_user(record)

    # Creates an admin-managed user with a one-time temporary password.
    def create_user_with_temp_password(self, payload: UserCreate) -> UserCreated:
        temporary_password = generate_temporary_password()
        record = self.repository.create_user(
            {
                "name": payload.name,
                "email": payload.email,
                "hashed_password": hash_password(temporary_password),
                "role": ROLE_USER,
                "status": STATUS_ACTIVE,
                "must_change_password": True,
                "last_login_at": None,
            }
        )
        public = to_public_user(record)
        return UserCreated(**public.model_dump(), temporary_password=temporary_password)

    # Returns the raw user record needed for backend auth checks.
    def get_user(self, user_id: str) -> dict[str, object] | None:
        return self.repository.get_by_id(user_id)

    # Finds a raw user record by normalized email.
    def get_user_by_email(self, email: str) -> dict[str, object] | None:
        return self.repository.get_by_email(normalize_email(email))

    # Returns one safe user response or raises a route-friendly error.
    def get_public_user(self, user_id: str) -> UserPublic:
        record = self.get_user(user_id)
        if not record:
            raise NotFoundError("User not found")
        return to_public_user(record)

    # Lists every safe user response for admin management.
    def list_users(self) -> list[UserPublic]:
        return [to_public_user(record) for record in self.repository.list_users()]

    # Applies the approved profile update fields.
    def update_user(self, user_id: str, payload: UserUpdate) -> UserPublic:
        record = self.repository.update_user(user_id, {"name": payload.name})
        if not record:
            raise NotFoundError("User not found")
        return to_public_user(record)

    # Changes the single account-status field used by auth checks.
    def set_status(self, user_id: str, status: str) -> UserPublic:
        record = self.repository.update_user(user_id, {"status": status})
        if not record:
            raise NotFoundError("User not found")
        return to_public_user(record)

    # Implements delete as reversible disabled status.
    def soft_disable(self, user_id: str) -> UserPublic:
        return self.set_status(user_id, STATUS_DISABLED)


# Encapsulates login, refresh rotation, logout, and password changes.
class AuthService:
    # Receives user and session repositories for auth workflows.
    def __init__(self, users: UserRepository, sessions: SessionRepository) -> None:
        self.users = users
        self.sessions = sessions

    # Verifies credentials and issues a fresh cookie/session set.
    def login(self, *, email: str, password: str, settings: IdentitySettings) -> AuthTokens:
        user = self.users.get_by_email(email)
        if not user or user.get("status") != STATUS_ACTIVE:
            raise AuthenticationError("Invalid email or password")
        if not verify_password(password, str(user["hashed_password"])):
            raise AuthenticationError("Invalid email or password")

        updated = self.users.update_user(str(user["id"]), {"last_login_at": now_iso()})
        if not updated:
            raise AuthenticationError("Invalid email or password")
        return self._issue_tokens(updated, settings)

    # Rotates a valid refresh token and revokes reused token families.
    def refresh(self, *, refresh_token: str, settings: IdentitySettings) -> AuthTokens:
        self.sessions.cleanup_expired()
        token_hash = hash_refresh_token(refresh_token)
        session = self.sessions.get_by_token_hash(token_hash)
        if not session:
            raise AuthenticationError("Invalid refresh session")
        if session.get("revoked") is True:
            self.sessions.revoke_family(str(session["family_id"]))
            raise AuthenticationError("Invalid refresh session")
        if self._is_expired(str(session["expires_at"])):
            self.sessions.revoke_session(str(session["id"]))
            raise AuthenticationError("Invalid refresh session")

        user = self.users.get_by_id(str(session["user_id"]))
        if not user or user.get("status") != STATUS_ACTIVE:
            self.sessions.revoke_family(str(session["family_id"]))
            raise AuthenticationError("Invalid refresh session")

        self.sessions.revoke_session(str(session["id"]))
        return self._issue_tokens(user, settings, family_id=str(session["family_id"]), rotated_from=str(session["id"]))

    # Revokes the current refresh session if one is presented.
    def logout(self, refresh_token: str | None) -> None:
        if not refresh_token:
            return
        session = self.sessions.get_by_token_hash(hash_refresh_token(refresh_token))
        if session:
            self.sessions.revoke_session(str(session["id"]))

    # Reauthenticates before replacing the hash and clearing first-login lockout.
    def change_password(
        self,
        *,
        user_id: str,
        current_password: str,
        new_password: str,
        current_refresh_token: str | None,
    ) -> dict[str, object]:
        user = self.users.get_by_id(user_id)
        if not user or user.get("status") != STATUS_ACTIVE:
            raise AuthenticationError("Invalid email or password")
        if not verify_password(current_password, str(user["hashed_password"])):
            raise AuthenticationError("Invalid email or password")

        current_session_id = None
        if current_refresh_token:
            session = self.sessions.get_by_token_hash(hash_refresh_token(current_refresh_token))
            if session and session.get("revoked") is not True:
                current_session_id = str(session["id"])

        updated = self.users.update_user(
            user_id,
            {
                "hashed_password": hash_password(new_password),
                "must_change_password": False,
            },
        )
        if not updated:
            raise AuthenticationError("Invalid email or password")

        self.sessions.revoke_user_sessions(user_id, except_session_id=current_session_id)
        return updated

    # Revokes every refresh session for a user after admin action.
    def revoke_all_for_user(self, user_id: str) -> None:
        self.sessions.revoke_user_sessions(user_id)

    # Reissues an access token after claims change without rotating refresh.
    def issue_access_token(self, user: dict[str, object], settings: IdentitySettings) -> str:
        return sign_access_token(user, settings)

    # Creates access, refresh, and CSRF tokens for one authenticated user.
    def _issue_tokens(
        self,
        user: dict[str, object],
        settings: IdentitySettings,
        *,
        family_id: str | None = None,
        rotated_from: str | None = None,
    ) -> AuthTokens:
        refresh_token = generate_refresh_token()
        session_family_id = family_id or str(uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
        self.sessions.create_session(
            {
                "user_id": str(user["id"]),
                "token_hash": hash_refresh_token(refresh_token),
                "family_id": session_family_id,
                "expires_at": expires_at.isoformat(),
                "revoked": False,
                "rotated_from": rotated_from,
            }
        )
        return AuthTokens(
            access_token=sign_access_token(user, settings),
            refresh_token=refresh_token,
            csrf_token=generate_csrf_token(),
            user=to_public_user(user),
        )

    # Compares persisted ISO expiry values against current UTC.
    def _is_expired(self, expires_at: str) -> bool:
        parsed = datetime.fromisoformat(expires_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed <= datetime.now(timezone.utc)
