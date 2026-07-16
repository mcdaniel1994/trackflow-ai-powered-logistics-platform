"""Static half of the Prefect release gate; Compose startup performs live checks."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VersionTuple = tuple[int, int, int]


def _version(value: str) -> VersionTuple:
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)", value)
    if match is None:
        raise RuntimeError("Prefect version is invalid")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def verify() -> tuple[VersionTuple, VersionTuple]:
    lock = tomllib.loads((ROOT / "data/uv.lock").read_text())
    client = next(
        _version(package["version"])
        for package in lock["package"]
        if package.get("name") == "prefect"
    )
    env_example = (ROOT / ".env.example").read_text()
    match = re.search(r"^PREFECT_SERVER_IMAGE=prefecthq/prefect:([0-9]+\.[0-9]+\.[0-9]+)-", env_example, re.MULTILINE)
    if match is None:
        raise RuntimeError("Pinned Prefect server image version is missing")
    server = _version(match.group(1))
    if server[0] != client[0] or server < client:
        raise RuntimeError("Pinned Prefect server must be the same major and not older than the client")

    compose = (ROOT / "compose.coolify.yaml").read_text()
    worker = (ROOT / "data/pipelines/business_performance/worker.py").read_text()
    required = (
        "PREFECT_API_DATABASE_CONNECTION_URL: postgresql+asyncpg://",
        "prefect-postgres-bootstrap: {condition: service_completed_successfully}",
        # The guards no longer gate startup, so the worker must enforce the same
        # conditions itself before it can claim any work. Its credential is passed
        # as discrete parts (a password may contain URL-reserved characters) and
        # uses the CONNECT-only guard role, never the read-everything backup role.
        "PREFECT_GUARD_DB_USER: prefect_guard",
        "PREFECT_GUARD_DB_PASSWORD: ${PREFECT_GUARD_DB_PASSWORD",
        "start_period:",
    )
    forbidden = (
        "./docker/prefect-postgres-init.sql:",
        "./docker/prefect-postgres-backup-role.sh:",
        # `up -d` stays attached until a `service_completed_successfully`
        # dependency exits. Gating the worker on the one-shot guards put them on
        # Coolify's command boundary, where a slow guard was killed as exit 255
        # with the containers removed by cleanup. Enforcement belongs in the
        # worker's own startup guard, not in the deploy critical path.
        "prefect-postgres-guard: {condition: service_completed_successfully}",
        "prefect-version-guard: {condition: service_completed_successfully}",
        # The guard credential must never be interpolated into a DSN string.
        "PREFECT_GUARD_DATABASE_URL:",
        "prefect_backup:${PREFECT_BACKUP_DB_PASSWORD",
    )
    postgres_dockerfile = (ROOT / "docker/prefect-postgres.Dockerfile").read_text()
    central_api_dockerfile = (ROOT / "docker/central-api.Dockerfile").read_text()
    if (
        any(value not in compose for value in required)
        or any(value in compose for value in forbidden)
        or "sqlite" in compose.lower()
        or not postgres_dockerfile.startswith("FROM postgres:16@sha256:")
        or "docker/prefect-postgres-bootstrap.sh" not in postgres_dockerfile
        or "docker/prefect-postgres-guard.sh" not in postgres_dockerfile
        or "/health/live" not in central_api_dockerfile
        or "verify_startup_contract()" not in worker
    ):
        raise RuntimeError("Production Compose Prefect guard contract is invalid")
    return client, server


def main() -> None:
    client, server = verify()
    print(
        "prefect_release_contract_complete "
        f"client={'.'.join(map(str, client))} minimum_server={'.'.join(map(str, server))}"
    )


if __name__ == "__main__":
    main()
