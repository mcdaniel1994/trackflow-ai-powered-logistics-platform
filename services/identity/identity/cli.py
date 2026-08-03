"""CLI helpers for identity administration."""

from __future__ import annotations

import argparse
import getpass

from .config import get_db_path, get_settings
from .oauth import OAuthError, OAuthService
from .repository import (
    DuplicateEmailError,
    TinyDBIdentityStore,
    TinyDBOAuthClientRepository,
    TinyDBOAuthCodeRepository,
    TinyDBUserRepository,
)
from .service import UserService


# Creates the first admin through local/server-side trust.
def create_admin(*, name: str, email: str, password: str) -> str:
    store = TinyDBIdentityStore(get_db_path())
    try:
        users = UserService(TinyDBUserRepository(store))
        user = users.create_admin(name=name, email=email, password=password)
        return user.id
    finally:
        store.close()


def revoke_sessions() -> tuple[int, int]:
    """Clear restored session state before the required signing-key rotation."""
    store = TinyDBIdentityStore(get_db_path())
    try:
        with store.lock:
            sessions = store.db.table("refresh_sessions")
            resets = store.db.table("password_resets")
            counts = (len(sessions), len(resets))
            sessions.truncate()
            resets.truncate()
            return counts
    finally:
        store.close()


def create_oauth_client(
    *,
    name: str,
    grants: frozenset[str],
    scopes: frozenset[str],
    resources: list[str],
    source_audiences: list[str],
) -> tuple[str, str]:
    """Create one confidential OAuth client and return its one-time secret."""
    store = TinyDBIdentityStore(get_db_path())
    try:
        service = OAuthService(
            TinyDBUserRepository(store),
            TinyDBOAuthClientRepository(store),
            TinyDBOAuthCodeRepository(store),
            get_settings(),
        )
        return service.register_confidential_client(
            client_name=name,
            grants=grants,
            scopes=scopes,
            resources=resources,
            source_audiences=source_audiences,
        )
    finally:
        store.close()


# Parses the admin bootstrap command without exposing passwords.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m identity.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create-admin")
    create_parser.add_argument("--name")
    create_parser.add_argument("--email")
    subparsers.add_parser("revoke-sessions")
    oauth_parser = subparsers.add_parser("create-oauth-client")
    oauth_parser.add_argument("--name", required=True)
    oauth_parser.add_argument("--grants", required=True)
    oauth_parser.add_argument("--scopes", required=True)
    oauth_parser.add_argument("--resources", required=True)
    oauth_parser.add_argument("--source-audiences", default="")

    args = parser.parse_args(argv)
    if args.command == "revoke-sessions":
        sessions, resets = revoke_sessions()
        print(f"Revoked {sessions} refresh sessions and {resets} password reset records.")
        return 0
    if args.command == "create-oauth-client":
        try:
            client_id, client_secret = create_oauth_client(
                name=args.name,
                grants=frozenset(value for value in args.grants.split(",") if value),
                scopes=frozenset(value for value in args.scopes.split(",") if value),
                resources=[value for value in args.resources.split(",") if value],
                source_audiences=[value for value in args.source_audiences.split(",") if value],
            )
        except OAuthError as exc:
            print(f"OAuth client was not created: {exc.description}")
            return 1
        print(f"Client ID: {client_id}")
        print(f"Client secret (shown once): {client_secret}")
        return 0

    name = args.name or input("Admin name: ").strip()
    email = args.email or input("Admin email: ").strip()
    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm admin password: ")
    if password != confirm:
        print("Passwords do not match.")
        return 1

    try:
        user_id = create_admin(name=name, email=email, password=password)
    except DuplicateEmailError:
        print("An admin or user with that email already exists.")
        return 1

    print(f"Admin created: {email.strip().casefold()} ({user_id})")
    return 0


# Exposes the script entrypoint used by pyproject metadata.
def entrypoint() -> None:
    raise SystemExit(main())


def revoke_entrypoint() -> None:
    """Expose a dedicated server-side executable without interactive parsing."""
    sessions, resets = revoke_sessions()
    print(f"Revoked {sessions} refresh sessions and {resets} password reset records.")


if __name__ == "__main__":
    entrypoint()
