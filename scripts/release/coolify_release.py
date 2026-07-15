"""Mutate one Coolify image tag, deploy it, and poll the deployment safely."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

_IMAGE_TAG = re.compile(r"^sha-[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]+$")
_SUCCESS = {"finished", "success", "succeeded", "completed"}
_FAILURE = {"failed", "failure", "cancelled", "canceled", "cancelled-by-user", "canceled-by-user", "error"}
_PENDING = {"queued", "pending", "in_progress", "in-progress", "running", ""}


class ReleaseError(RuntimeError):
    """A fixed, non-sensitive Coolify release failure."""


@dataclass(frozen=True)
class ReleaseResult:
    previous_image_tag: str
    deployment_uuid: str


class CoolifyClient:
    def __init__(self, *, api_base: str, token: str, webhook: str) -> None:
        self.api_base = api_base.rstrip("/")
        self.token = token
        self.webhook = webhook

    def request_json(self, url: str, *, method: str = "GET", payload: object | None = None) -> Any:
        data = None if payload is None else json.dumps(payload, separators=(",", ":")).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 - validated HTTPS below
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise ReleaseError("Coolify request failed") from exc

    def environments(self, application_uuid: str) -> list[dict[str, Any]]:
        value = self.request_json(f"{self.api_base}/applications/{application_uuid}/envs")
        if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
            raise ReleaseError("Coolify environment response is invalid")
        return value

    def update_environment(self, application_uuid: str, payload: dict[str, Any]) -> None:
        self.request_json(
            f"{self.api_base}/applications/{application_uuid}/envs",
            method="PATCH",
            payload=payload,
        )

    def trigger(self) -> str:
        value = self.request_json(self.webhook)
        candidates: list[Any]
        if isinstance(value, list):
            candidates = value
        elif isinstance(value, dict):
            deployments = value.get("deployments")
            candidates = deployments if isinstance(deployments, list) else [value.get("data"), value]
        else:
            candidates = []
        for candidate in candidates:
            if isinstance(candidate, dict):
                deployment_uuid = candidate.get("deployment_uuid") or candidate.get("uuid")
                if isinstance(deployment_uuid, str) and _IDENTIFIER.fullmatch(deployment_uuid):
                    return deployment_uuid
        raise ReleaseError("Coolify deployment identifier is invalid")

    def deployment_status(self, deployment_uuid: str) -> str:
        value = self.request_json(f"{self.api_base}/deployments/{deployment_uuid}")
        if not isinstance(value, dict):
            raise ReleaseError("Coolify deployment response is invalid")
        data = value.get("data")
        status = value.get("status") or (data.get("status") if isinstance(data, dict) else None) or ""
        return str(status).lower()


def _target_record(environments: list[dict[str, Any]]) -> dict[str, Any]:
    targets = [
        item
        for item in environments
        if item.get("key") == "TRACKFLOW_IMAGE_TAG" and item.get("is_preview") is False
    ]
    if len(targets) != 1:
        raise ReleaseError("Expected exactly one production image-tag variable")
    target = targets[0]
    if not isinstance(target.get("uuid"), str) or not _IDENTIFIER.fullmatch(target["uuid"]):
        raise ReleaseError("Production image-tag variable identifier is invalid")
    boolean_fields = ("is_preview", "is_literal", "is_multiline", "is_shown_once", "is_buildtime", "is_runtime")
    if any(not isinstance(target.get(field), bool) for field in boolean_fields):
        raise ReleaseError("Production image-tag metadata is invalid")
    if target["is_buildtime"] is not True or target["is_runtime"] is not True:
        raise ReleaseError("Production image tag must be available at build time and runtime")
    return target


def _metadata(record: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "uuid",
        "key",
        "is_preview",
        "is_literal",
        "is_multiline",
        "is_shown_once",
        "is_buildtime",
        "is_runtime",
        "comment",
    )
    return {field: record.get(field) for field in fields}


def _other_records_digest(environments: list[dict[str, Any]], target_uuid: str) -> str:
    others = [item for item in environments if item.get("uuid") != target_uuid]
    encoded = json.dumps(others, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def deploy(
    client: CoolifyClient,
    *,
    application_uuid: str,
    target_image_tag: str,
    poll_attempts: int = 45,
    poll_interval_seconds: float = 20,
    on_previous_image_tag: Callable[[str], None] | None = None,
) -> ReleaseResult:
    if not _IMAGE_TAG.fullmatch(target_image_tag):
        raise ReleaseError("Image tag is not an immutable SHA")
    if not _IDENTIFIER.fullmatch(application_uuid):
        raise ReleaseError("Coolify application identifier is invalid")

    before = client.environments(application_uuid)
    target = _target_record(before)
    previous = target.get("value")
    if not isinstance(previous, str) or not _IMAGE_TAG.fullmatch(previous):
        raise ReleaseError("Previous production image tag is not rollback-safe")
    if on_previous_image_tag is not None:
        on_previous_image_tag(previous)
    target_uuid = str(target["uuid"])
    payload = {
        "key": target["key"],
        "value": target_image_tag,
        "is_preview": target["is_preview"],
        "is_literal": target["is_literal"],
        "is_multiline": target["is_multiline"],
        "is_shown_once": target["is_shown_once"],
        "is_buildtime": target["is_buildtime"],
        "is_runtime": target["is_runtime"],
        "comment": target.get("comment"),
    }
    client.update_environment(application_uuid, payload)

    after = client.environments(application_uuid)
    updated = _target_record(after)
    if len(after) != len(before) or _other_records_digest(after, target_uuid) != _other_records_digest(before, target_uuid):
        raise ReleaseError("Coolify changed an environment record outside the image tag")
    if _metadata(updated) != _metadata(target) or updated.get("value") != target_image_tag:
        raise ReleaseError("Coolify image-tag update verification failed")

    deployment_uuid = client.trigger()
    for attempt in range(poll_attempts):
        status = client.deployment_status(deployment_uuid)
        if status in _SUCCESS:
            return ReleaseResult(previous, deployment_uuid)
        if status in _FAILURE or status not in _PENDING:
            raise ReleaseError("Coolify deployment failed")
        if attempt + 1 < poll_attempts:
            time.sleep(poll_interval_seconds)
    raise ReleaseError("Coolify deployment timed out")


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ReleaseError(f"{name} is required")
    return value


def entrypoint() -> None:
    try:
        base_url = _required("COOLIFY_BASE_URL")
        webhook = _required("COOLIFY_WEBHOOK")
        if not re.fullmatch(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?", base_url):
            raise ReleaseError("Coolify base URL is invalid")
        if not webhook.startswith("https://") or any(character.isspace() for character in webhook):
            raise ReleaseError("Coolify webhook is invalid")
        github_env = os.environ.get("GITHUB_ENV")

        def capture_previous(image_tag: str) -> None:
            if github_env and os.environ.get("CAPTURE_PREVIOUS_IMAGE_TAG", "true").lower() == "true":
                with open(github_env, "a", encoding="utf-8") as environment_file:
                    environment_file.write(f"PREVIOUS_IMAGE_TAG={image_tag}\n")

        result = deploy(
            CoolifyClient(
                api_base=f"{base_url}/api/v1",
                token=_required("COOLIFY_TOKEN"),
                webhook=webhook,
            ),
            application_uuid=_required("COOLIFY_APPLICATION_UUID"),
            target_image_tag=_required("TARGET_IMAGE_TAG"),
            poll_attempts=int(os.environ.get("COOLIFY_POLL_ATTEMPTS", "45")),
            poll_interval_seconds=float(os.environ.get("COOLIFY_POLL_INTERVAL_SECONDS", "20")),
            on_previous_image_tag=capture_previous,
        )
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::add-mask::{result.deployment_uuid}")
        print("coolify_deployment_complete")
    except Exception as exc:
        print(f"coolify_release_failed error_type={type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    entrypoint()
