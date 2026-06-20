"""CLI helpers for identity administration."""

from __future__ import annotations

import argparse
import getpass

from .config import get_db_path
from .repository import DuplicateEmailError, TinyDBIdentityStore, TinyDBUserRepository
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


# Parses the admin bootstrap command without exposing passwords.
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m identity.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)
    create_parser = subparsers.add_parser("create-admin")
    create_parser.add_argument("--name")
    create_parser.add_argument("--email")

    args = parser.parse_args(argv)
    if args.command != "create-admin":
        parser.error("Unsupported command")

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


if __name__ == "__main__":
    entrypoint()
