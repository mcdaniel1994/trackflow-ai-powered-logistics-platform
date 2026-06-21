"""TinyDB repositories for identity users and refresh sessions."""

from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import uuid4

from tinydb import Query, TinyDB

from .models import normalize_email
from .security import now_iso, now_utc


# Signals email uniqueness conflicts before user creation completes.
class DuplicateEmailError(ValueError):
    """Raised when an email is already registered."""


# Defines the user persistence boundary for future SQL replacement.
class UserRepository(Protocol):
    # Inserts a normalized user record with a generated stable id.
    def create_user(self, data: dict[str, object]) -> dict[str, object]: ...
    # Finds one user by the UUID stored in auth claims.
    def get_by_id(self, user_id: str) -> dict[str, object] | None: ...
    # Finds one user by normalized email for login and uniqueness.
    def get_by_email(self, email: str) -> dict[str, object] | None: ...
    # Returns all users for the admin management endpoint.
    def list_users(self) -> list[dict[str, object]]: ...
    # Applies controlled field changes to an existing user.
    def update_user(self, user_id: str, changes: dict[str, object]) -> dict[str, object] | None: ...


# Defines the refresh-session boundary for token rotation and revocation.
class SessionRepository(Protocol):
    # Persists a hashed refresh token and its token-family metadata.
    def create_session(self, data: dict[str, object]) -> dict[str, object]: ...
    # Looks up the presented refresh token by its stored digest.
    def get_by_token_hash(self, token_hash: str) -> dict[str, object] | None: ...
    # Finds one refresh session by its generated session id.
    def get_by_id(self, session_id: str) -> dict[str, object] | None: ...
    # Revokes one refresh session after use or logout.
    def revoke_session(self, session_id: str) -> None: ...
    # Revokes a whole token family after refresh-token reuse.
    def revoke_family(self, family_id: str) -> None: ...
    # Revokes a user's sessions, optionally keeping the current one.
    def revoke_user_sessions(self, user_id: str, except_session_id: str | None = None) -> None: ...
    # Marks expired refresh sessions revoked before rotation checks.
    def cleanup_expired(self) -> None: ...


# Defines the password-reset boundary for one-time account recovery tokens.
class PasswordResetRepository(Protocol):
    # Persists only the hashed opaque reset token.
    def create_reset(self, data: dict[str, object]) -> dict[str, object]: ...
    # Finds one reset record by the digest of the presented token.
    def get_by_token_hash(self, token_hash: str) -> dict[str, object] | None: ...
    # Marks a reset token consumed after a successful password reset.
    def mark_used(self, reset_id: str) -> dict[str, object] | None: ...
    # Invalidates outstanding reset tokens for a user.
    def invalidate_user_tokens(self, user_id: str) -> None: ...
    # Marks expired reset tokens used so they cannot be replayed.
    def cleanup_expired(self) -> None: ...


# Owns the TinyDB handle and write lock shared by both repositories.
class TinyDBIdentityStore:
    # Opens the identity TinyDB file and prepares coordinated writes.
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = TinyDB(str(self.db_path))
        self.lock = RLock()

    # Closes the TinyDB handle on FastAPI shutdown or CLI exit.
    def close(self) -> None:
        self.db.close()


# Implements user persistence with TinyDB collections.
class TinyDBUserRepository:
    # Binds this repository to the shared identity TinyDB store.
    def __init__(self, store: TinyDBIdentityStore) -> None:
        self.store = store
        self.table = self.store.db.table("users")

    # Enforces normalized-email uniqueness before inserting.
    def create_user(self, data: dict[str, object]) -> dict[str, object]:
        with self.store.lock:
            email = normalize_email(str(data["email"]))
            if self.get_by_email(email):
                raise DuplicateEmailError("Email is already registered")

            record = dict(data)
            record["id"] = str(uuid4())
            record["email"] = email
            record["created_at"] = now_iso()
            record.setdefault("last_login_at", None)
            self.table.insert(record)
            return record

    # Reads a user by stable UUID instead of TinyDB document id.
    def get_by_id(self, user_id: str) -> dict[str, object] | None:
        user = Query()
        record = self.table.get(user.id == user_id)
        return dict(record) if record else None

    # Reads a user by casefolded email for login and duplicates.
    def get_by_email(self, email: str) -> dict[str, object] | None:
        user = Query()
        record = self.table.get(user.email == normalize_email(email))
        return dict(record) if record else None

    # Lists users in deterministic email order for admin screens.
    def list_users(self) -> list[dict[str, object]]:
        records = [dict(record) for record in self.table.all()]
        return sorted(records, key=lambda record: str(record.get("email", "")))

    # Applies repository-approved changes and returns the latest record.
    def update_user(self, user_id: str, changes: dict[str, object]) -> dict[str, object] | None:
        with self.store.lock:
            user = Query()
            updated = self.table.update(dict(changes), user.id == user_id)
            if not updated:
                return None
            return self.get_by_id(user_id)


# Implements refresh-session persistence with TinyDB collections.
class TinyDBSessionRepository:
    # Binds refresh-session operations to the shared TinyDB store.
    def __init__(self, store: TinyDBIdentityStore) -> None:
        self.store = store
        self.table = self.store.db.table("refresh_sessions")

    # Inserts a refresh session with a generated stable id.
    def create_session(self, data: dict[str, object]) -> dict[str, object]:
        with self.store.lock:
            record = dict(data)
            record["id"] = str(uuid4())
            record["created_at"] = now_iso()
            self.table.insert(record)
            return record

    # Finds a refresh session without storing the raw token.
    def get_by_token_hash(self, token_hash: str) -> dict[str, object] | None:
        session = Query()
        record = self.table.get(session.token_hash == token_hash)
        return dict(record) if record else None

    # Finds one session by stable session id.
    def get_by_id(self, session_id: str) -> dict[str, object] | None:
        session = Query()
        record = self.table.get(session.id == session_id)
        return dict(record) if record else None

    # Marks one session revoked while preserving audit state.
    def revoke_session(self, session_id: str) -> None:
        with self.store.lock:
            session = Query()
            self.table.update({"revoked": True}, session.id == session_id)

    # Kills every session in a refresh-token family.
    def revoke_family(self, family_id: str) -> None:
        with self.store.lock:
            session = Query()
            self.table.update({"revoked": True}, session.family_id == family_id)

    # Revokes all sessions for logout-everywhere style actions.
    def revoke_user_sessions(self, user_id: str, except_session_id: str | None = None) -> None:
        with self.store.lock:
            session = Query()
            for record in self.table.search(session.user_id == user_id):
                if except_session_id and record.get("id") == except_session_id:
                    continue
                self.table.update({"revoked": True}, doc_ids=[record.doc_id])

    # Marks expired sessions revoked so refresh cannot reuse them.
    def cleanup_expired(self) -> None:
        with self.store.lock:
            session = Query()
            expired_ids = [
                record.doc_id
                for record in self.table.search(session.revoked == False)  # noqa: E712
                if str(record.get("expires_at", "")) <= now_utc().isoformat()
            ]
            if expired_ids:
                self.table.update({"revoked": True}, doc_ids=expired_ids)


# Implements password-reset persistence with TinyDB collections.
class TinyDBPasswordResetRepository:
    # Binds reset-token operations to the shared TinyDB store.
    def __init__(self, store: TinyDBIdentityStore) -> None:
        self.store = store
        self.table = self.store.db.table("password_resets")

    # Inserts a reset record with a generated stable id.
    def create_reset(self, data: dict[str, object]) -> dict[str, object]:
        with self.store.lock:
            record = dict(data)
            record["id"] = str(uuid4())
            record["created_at"] = now_iso()
            self.table.insert(record)
            return record

    # Finds a reset token without storing the raw token.
    def get_by_token_hash(self, token_hash: str) -> dict[str, object] | None:
        reset = Query()
        record = self.table.get(reset.token_hash == token_hash)
        return dict(record) if record else None

    # Marks a reset record used while preserving the audit fields.
    def mark_used(self, reset_id: str) -> dict[str, object] | None:
        with self.store.lock:
            reset = Query()
            updated = self.table.update({"used": True}, reset.id == reset_id)
            if not updated:
                return None
            record = self.table.get(reset.id == reset_id)
            return dict(record) if record else None

    # Invalidates every outstanding reset token for one user.
    def invalidate_user_tokens(self, user_id: str) -> None:
        with self.store.lock:
            reset = Query()
            for record in self.table.search(reset.user_id == user_id):
                if record.get("used") is True:
                    continue
                self.table.update({"used": True}, doc_ids=[record.doc_id])

    # Marks expired reset tokens used so future reads fail safely.
    def cleanup_expired(self) -> None:
        with self.store.lock:
            reset = Query()
            expired_ids = [
                record.doc_id
                for record in self.table.search(reset.used == False)  # noqa: E712
                if str(record.get("expires_at", "")) <= now_utc().isoformat()
            ]
            if expired_ids:
                self.table.update({"used": True}, doc_ids=expired_ids)
