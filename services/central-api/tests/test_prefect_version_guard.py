"""Prefect client/server startup compatibility gate."""

import pytest
from packaging.version import Version

from scripts import prefect_version_guard
from scripts.prefect_version_guard import verify_compatibility


def test_server_must_be_same_major_and_not_older() -> None:
    verify_compatibility(client=Version("3.7.8"), server=Version("3.7.8"))
    verify_compatibility(client=Version("3.7.8"), server=Version("3.8.0"))
    # Rejections carry fixed reason slugs so a failed deployment names its cause.
    with pytest.raises(RuntimeError, match="server_older_than_client"):
        verify_compatibility(client=Version("3.7.8"), server=Version("3.7.7"))
    with pytest.raises(RuntimeError, match="server_major_mismatch"):
        verify_compatibility(client=Version("3.7.8"), server=Version("4.0.0"))


def test_server_version_requires_the_approved_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    digest = next(iter(prefect_version_guard.KNOWN_SERVER_DIGESTS))
    monkeypatch.setenv(
        "PREFECT_SERVER_IMAGE_REF",
        f"prefecthq/prefect:3.7.8-python3.11@sha256:{digest}",
    )
    assert prefect_version_guard.server_version() == Version("3.7.8")
    monkeypatch.setenv(
        "PREFECT_SERVER_IMAGE_REF",
        f"prefecthq/prefect:3.7.9-python3.11@sha256:{digest}",
    )
    with pytest.raises(RuntimeError, match="server_digest_not_approved"):
        prefect_version_guard.server_version()
