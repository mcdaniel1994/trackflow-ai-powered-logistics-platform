"""Compatibility rules between the Prefect client and its dedicated server.

This lives in `data` because both consumers depend on it from here: the
`prefect-version-guard` container (via `scripts.prefect_version_guard`) and the
reporting worker's own fail-closed startup guard. `central-api` depends on
`trackflow-data-pipelines`, so putting it here keeps the dependency pointing one
way.
"""

from __future__ import annotations

import importlib.metadata
import os
import re

from packaging.version import Version

KNOWN_SERVER_DIGESTS = {
    "d4d142f1426ed0e8d7f48b3cc730f7b0469dcbcaf720959bb678f4cec3e5c3cc": Version("3.7.8")
}


class GuardFailure(RuntimeError):
    """Guard rejection carrying a fixed reason slug safe to log."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def client_version() -> Version:
    return Version(importlib.metadata.version("prefect"))


def server_version() -> Version:
    image_ref = os.environ.get("PREFECT_SERVER_IMAGE_REF", "")
    match = re.fullmatch(
        r"prefecthq/prefect:([0-9]+\.[0-9]+\.[0-9]+)-python3\.11@sha256:([0-9a-f]{64})",
        image_ref,
    )
    if match is None:
        raise GuardFailure("server_image_reference_invalid")
    tagged = Version(match.group(1))
    mapped = KNOWN_SERVER_DIGESTS.get(match.group(2))
    if mapped is None or mapped != tagged:
        raise GuardFailure("server_digest_not_approved")
    return mapped


def verify_compatibility(*, client: Version, server: Version) -> None:
    if server.major != client.major:
        raise GuardFailure("server_major_mismatch")
    if server < client:
        raise GuardFailure("server_older_than_client")
