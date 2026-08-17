"""Mocked Coolify success, failure, and rollback-target safety tests."""

from __future__ import annotations

import importlib.util
import io
import sys
import urllib.error
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
ReleaseResult = MODULE.ReleaseResult
deploy = MODULE.deploy
CoolifyClient = MODULE.CoolifyClient

OLD_TAG = "sha-" + "1" * 40
NEW_TAG = "sha-" + "2" * 40


class JsonResponse(io.BytesIO):
    def __enter__(self) -> JsonResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


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


def test_entrypoint_never_emits_deployment_identifier(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    deployment_identifier = "sensitive-deployment-coordinate"
    monkeypatch.setenv("COOLIFY_BASE_URL", "https://coolify.example.test")
    monkeypatch.setenv("COOLIFY_WEBHOOK", "https://coolify.example.test/webhook")
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    monkeypatch.setenv("COOLIFY_APPLICATION_UUID", "application-uuid")
    monkeypatch.setenv("TARGET_IMAGE_TAG", NEW_TAG)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setattr(
        MODULE,
        "deploy",
        lambda *args, **kwargs: ReleaseResult(OLD_TAG, deployment_identifier),
    )

    MODULE.entrypoint()

    captured = capsys.readouterr()
    assert captured.out == "coolify_deployment_complete\n"
    assert deployment_identifier not in captured.out
    assert captured.err == ""


def test_idempotent_get_retries_transient_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    outcomes: list[object] = [
        TimeoutError(),
        urllib.error.URLError("temporary"),
        JsonResponse(b'{"status":"finished"}'),
    ]
    calls = 0
    sleeps: list[int] = []

    def urlopen(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        outcome = outcomes[calls]
        calls += 1
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(MODULE.time, "sleep", sleeps.append)
    client = CoolifyClient(
        api_base="https://coolify.example.test/api/v1",
        token="test-token",
        webhook="https://coolify.example.test/webhook",
    )

    assert client.request_json(
        "https://coolify.example.test/api/v1/applications/app/envs",
        retry_transient_get=True,
    ) == {"status": "finished"}
    assert calls == 3
    assert sleeps == [2, 4]


def test_deployment_webhook_posts_and_is_never_retried(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Any] = []

    def urlopen(request: Any, *_args: object, **_kwargs: object) -> object:
        requests.append(request)
        raise TimeoutError

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        MODULE.time,
        "sleep",
        lambda _seconds: pytest.fail("deployment webhook must not retry"),
    )
    client = CoolifyClient(
        api_base="https://coolify.example.test/api/v1",
        token="test-token",
        webhook="https://coolify.example.test/webhook",
    )

    with pytest.raises(ReleaseError) as failure:
        client.trigger()
    assert failure.value.reason == "coolify_request_failed"
    assert len(requests) == 1
    assert requests[0].get_method() == "POST"


def test_deployment_webhook_posts_and_parses_deployment_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Any] = []

    def urlopen(request: Any, *_args: object, **_kwargs: object) -> object:
        requests.append(request)
        return JsonResponse(b'{"deployments":[{"deployment_uuid":"deployment-uuid"}]}')

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", urlopen)
    client = CoolifyClient(
        api_base="https://coolify.example.test/api/v1",
        token="test-token",
        webhook="https://coolify.example.test/webhook",
    )

    assert client.trigger() == "deployment-uuid"
    assert requests[0].get_method() == "POST"


def test_idempotent_get_does_not_retry_client_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def urlopen(*_args: object, **_kwargs: object) -> object:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(
            "https://coolify.example.test",
            401,
            "unauthorized",
            {},
            None,
        )

    monkeypatch.setattr(MODULE.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(
        MODULE.time,
        "sleep",
        lambda _seconds: pytest.fail("client errors must not retry"),
    )
    client = CoolifyClient(
        api_base="https://coolify.example.test/api/v1",
        token="test-token",
        webhook="https://coolify.example.test/webhook",
    )

    with pytest.raises(ReleaseError) as failure:
        client.environments("application-uuid")
    assert failure.value.reason == "coolify_http_error"
    assert calls == 1


def test_entrypoint_emits_only_sanitized_release_reason(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("COOLIFY_BASE_URL", "https://coolify.example.test")
    monkeypatch.setenv("COOLIFY_WEBHOOK", "https://coolify.example.test/webhook")
    monkeypatch.setenv("COOLIFY_TOKEN", "test-token")
    monkeypatch.setenv("COOLIFY_APPLICATION_UUID", "application-uuid")
    monkeypatch.setenv("TARGET_IMAGE_TAG", NEW_TAG)
    monkeypatch.setattr(
        MODULE,
        "deploy",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ReleaseError(
                "sensitive internal detail",
                reason="coolify_get_transient_exhausted",
            )
        ),
    )

    with pytest.raises(SystemExit):
        MODULE.entrypoint()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == (
        "coolify_release_failed error_type=ReleaseError "
        "reason=coolify_get_transient_exhausted\n"
    )
    assert "sensitive internal detail" not in captured.err
