"""Fail startup when the app's Prefect client is newer than its dedicated server.

The compatibility rules live in `pipelines.business_performance.prefect_version`
so the reporting worker's startup guard enforces the identical logic. This module
is the container entrypoint over them.
"""

from __future__ import annotations

import sys

from pipelines.business_performance.prefect_version import (
    KNOWN_SERVER_DIGESTS,
    GuardFailure,
    client_version,
    server_version,
    verify_compatibility,
)

__all__ = [
    "KNOWN_SERVER_DIGESTS",
    "GuardFailure",
    "client_version",
    "main",
    "server_version",
    "verify_compatibility",
]


def main() -> None:
    try:
        client = client_version()
        server = server_version()
        verify_compatibility(client=client, server=server)
    except GuardFailure as failure:
        # A fixed token so a failed deployment names the guard that rejected it
        # instead of surfacing only an opaque non-zero exit.
        print(f"prefect_version_guard=failed reason={failure.reason}")
        sys.exit(1)
    print(f"prefect_version_guard_complete client={client} server={server}")


if __name__ == "__main__":
    main()
