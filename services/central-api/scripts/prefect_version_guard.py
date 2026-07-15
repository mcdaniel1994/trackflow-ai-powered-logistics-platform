"""Fail startup when the app's Prefect client is newer than its dedicated server."""

from __future__ import annotations

import importlib.metadata
import os
import re

from packaging.version import Version

KNOWN_SERVER_DIGESTS = {
    "d4d142f1426ed0e8d7f48b3cc730f7b0469dcbcaf720959bb678f4cec3e5c3cc": Version("3.7.8")
}


def server_version() -> Version:
    image_ref = os.environ.get("PREFECT_SERVER_IMAGE_REF", "")
    match = re.fullmatch(
        r"prefecthq/prefect:([0-9]+\.[0-9]+\.[0-9]+)-python3\.11@sha256:([0-9a-f]{64})",
        image_ref,
    )
    if match is None:
        raise RuntimeError("Prefect server image reference is invalid")
    tagged = Version(match.group(1))
    mapped = KNOWN_SERVER_DIGESTS.get(match.group(2))
    if mapped is None or mapped != tagged:
        raise RuntimeError("Prefect server digest is not approved for its tagged version")
    return mapped


def verify_compatibility(*, client: Version, server: Version) -> None:
    if server.major != client.major or server < client:
        raise RuntimeError("Prefect server must be the same major and not older than the client")


def main() -> None:
    client = Version(importlib.metadata.version("prefect"))
    server = server_version()
    verify_compatibility(client=client, server=server)
    print(f"prefect_version_guard_complete client={client} server={server}")


if __name__ == "__main__":
    main()
