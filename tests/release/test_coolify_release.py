"""Mocked Coolify success, failure, and rollback-target safety tests."""

from __future__ import annotations

import importlib.util
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "release" / "coolify_release.py"
SPEC = importlib.util.spec_from_file_location("trackflow_coolify_release", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
ReleaseError = MODULE.ReleaseError
deploy = MODULE.deploy

OLD_TAG = "sha-" + "1" * 40
NEW_TAG = "sha-" + "2" * 40


def _environments() -> list[dict[str, Any]]:
    return [
        {
            "uuid": "image-tag-uuid",
            "key": "TRACKFLOW_IMAGE_TAG",
            "value": OLD_TAG,
            "is_preview": False,
            "is_literal": True,
            "is_multiline": False,
            "is_shown_once": False,
            "is_buildtime": True,
            "is_runtime": True,
            "comment": "immutable image",
        },
        {
            "uuid": "database-uuid",
            "key": "DATABASE_URL",
            "value": "private-value",
            "is_preview": False,
        },
    ]


class FakeClient:
    def __init__(self, statuses: list[str]) -> None:
        self.records = _environments()
        self.statuses = iter(statuses)
        self.updated_payload: dict[str, Any] | None = None

    def environments(self, _application_uuid: str) -> list[dict[str, Any]]:
        return deepcopy(self.records)

    def update_environment(self, _application_uuid: str, payload: dict[str, Any]) -> None:
        self.updated_payload = payload
        self.records[0]["value"] = payload["value"]

    def trigger(self) -> str:
        return "deployment-uuid"

    def deployment_status(self, _deployment_uuid: str) -> str:
        return next(self.statuses)


def test_deploy_preserves_other_records_and_returns_rollback_tag() -> None:
    client = FakeClient(["running", "finished"])
    result = deploy(  # type: ignore[arg-type]
        client,
        application_uuid="application-uuid",
        target_image_tag=NEW_TAG,
        poll_attempts=2,
        poll_interval_seconds=0,
    )
    assert result.previous_image_tag == OLD_TAG
    assert client.records[1] == _environments()[1]
    assert client.updated_payload is not None
    assert client.updated_payload["value"] == NEW_TAG


@pytest.mark.parametrize("statuses", [["failed"], ["mystery"], ["running"]])
def test_deploy_fails_closed_for_failure_unknown_and_timeout(statuses: list[str]) -> None:
    with pytest.raises(ReleaseError):
        deploy(  # type: ignore[arg-type]
            FakeClient(statuses),
            application_uuid="application-uuid",
            target_image_tag=NEW_TAG,
            poll_attempts=len(statuses),
            poll_interval_seconds=0,
        )


def test_deploy_requires_known_sha_previous_and_target() -> None:
    client = FakeClient(["finished"])
    client.records[0]["value"] = "main"
    with pytest.raises(ReleaseError, match="rollback-safe"):
        deploy(client, application_uuid="application-uuid", target_image_tag=NEW_TAG)  # type: ignore[arg-type]
    with pytest.raises(ReleaseError, match="immutable SHA"):
        deploy(client, application_uuid="application-uuid", target_image_tag="main")  # type: ignore[arg-type]


def test_failed_deployment_preserves_target_for_automatic_image_rollback() -> None:
    client = FakeClient(["failed"])
    captured: list[str] = []
    with pytest.raises(ReleaseError):
        deploy(  # type: ignore[arg-type]
            client,
            application_uuid="application-uuid",
            target_image_tag=NEW_TAG,
            poll_attempts=1,
            poll_interval_seconds=0,
            on_previous_image_tag=captured.append,
        )
    assert captured == [OLD_TAG]
    assert client.records[0]["value"] == NEW_TAG

    client.statuses = iter(["finished"])
    rollback = deploy(  # type: ignore[arg-type]
        client,
        application_uuid="application-uuid",
        target_image_tag=captured[0],
        poll_attempts=1,
        poll_interval_seconds=0,
    )
    assert rollback.previous_image_tag == NEW_TAG
    assert client.records[0]["value"] == OLD_TAG
