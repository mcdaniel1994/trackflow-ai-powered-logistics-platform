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
    required = (
        "PREFECT_API_DATABASE_CONNECTION_URL: postgresql+asyncpg://",
        "prefect-postgres-guard: {condition: service_completed_successfully}",
        "prefect-version-guard: {condition: service_completed_successfully}",
    )
    if any(value not in compose for value in required) or "sqlite" in compose.lower():
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
