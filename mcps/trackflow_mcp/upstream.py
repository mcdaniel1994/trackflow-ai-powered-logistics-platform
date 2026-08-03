"""Delegated OAuth exchange and bounded Central API access."""

from __future__ import annotations

from typing import Any

import httpx

from .config import MCPSettings
from .errors import ErrorCode, ToolFailure

TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
TRANSIENT_STATUSES = {502, 503, 504}


class CentralAPIClient:
    def __init__(self, settings: MCPSettings) -> None:
        self.settings = settings
        self.timeout = httpx.Timeout(
            connect=settings.upstream_connect_timeout_seconds,
            read=settings.upstream_read_timeout_seconds,
            write=settings.upstream_read_timeout_seconds,
            pool=settings.upstream_connect_timeout_seconds,
        )

    async def request(
        self,
        *,
        method: str,
        path: str,
        subject_token: str,
        scopes: frozenset[str],
        json: dict[str, object] | None = None,
        params: dict[str, str | int | float | bool | None] | None = None,
        idempotent: bool = False,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                delegated = await self._exchange(client, subject_token, scopes)
                attempts = 2 if idempotent else 1
                response: httpx.Response | None = None
                for attempt in range(attempts):
                    try:
                        response = await client.request(
                            method,
                            f"{self.settings.central_api_url}{path}",
                            headers={"Authorization": f"Bearer {delegated}"},
                            json=json,
                            params=params,
                        )
                    except (httpx.ConnectError, httpx.ReadError) as exc:
                        if attempt + 1 == attempts:
                            raise ToolFailure(
                                ErrorCode.UPSTREAM_UNAVAILABLE,
                                "The operations API is unavailable.",
                            ) from exc
                        continue
                    if response.status_code not in TRANSIENT_STATUSES or attempt + 1 == attempts:
                        break
        except httpx.TimeoutException as exc:
            raise ToolFailure(ErrorCode.UPSTREAM_TIMEOUT, "The operations API timed out.") from exc
        except ToolFailure:
            raise
        except httpx.HTTPError as exc:
            raise ToolFailure(ErrorCode.UPSTREAM_UNAVAILABLE, "The operations API is unavailable.") from exc

        if response is None:
            raise ToolFailure(ErrorCode.UPSTREAM_UNAVAILABLE, "The operations API is unavailable.")
        self._raise_for_status(response)
        try:
            payload = response.json()
        except ValueError as exc:
            raise ToolFailure(
                ErrorCode.UPSTREAM_UNAVAILABLE,
                "The operations API returned an invalid response.",
            ) from exc
        if not isinstance(payload, dict):
            raise ToolFailure(ErrorCode.UPSTREAM_UNAVAILABLE, "The operations API returned an invalid response.")
        return payload

    async def _exchange(
        self,
        client: httpx.AsyncClient,
        subject_token: str,
        scopes: frozenset[str],
    ) -> str:
        response = await client.post(
            self.settings.oauth_token_url,
            auth=(self.settings.oauth_client_id, self.settings.oauth_client_secret.get_secret_value()),
            data={
                "grant_type": TOKEN_EXCHANGE_GRANT,
                "subject_token": subject_token,
                "subject_token_type": ACCESS_TOKEN_TYPE,
                "resource": self.settings.central_api_oauth_resource_url,
                "scope": " ".join(sorted(scopes)),
            },
        )
        if response.status_code in {401, 403}:
            raise ToolFailure(ErrorCode.AUTHENTICATION_REQUIRED, "Delegated authorization was rejected.")
        if response.status_code >= 500:
            raise ToolFailure(ErrorCode.UPSTREAM_UNAVAILABLE, "The authorization service is unavailable.")
        if response.status_code >= 400:
            raise ToolFailure(ErrorCode.INSUFFICIENT_SCOPE, "Delegated authorization is insufficient.")
        try:
            token = response.json().get("access_token")
        except (AttributeError, ValueError) as exc:
            raise ToolFailure(
                ErrorCode.UPSTREAM_UNAVAILABLE,
                "The authorization service returned an invalid response.",
            ) from exc
        if not isinstance(token, str) or not token:
            raise ToolFailure(ErrorCode.UPSTREAM_UNAVAILABLE, "The authorization service returned an invalid response.")
        return token

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code == 404:
            raise ToolFailure(ErrorCode.NOT_FOUND, "The requested record was not found.")
        if response.status_code == 409:
            raise ToolFailure(ErrorCode.INVALID_TRANSITION, "The requested ticket transition is not allowed.")
        if response.status_code in {400, 422}:
            raise ToolFailure(ErrorCode.INVALID_INPUT, "The request was invalid.")
        if response.status_code in {401, 403}:
            raise ToolFailure(ErrorCode.INSUFFICIENT_SCOPE, "Delegated authorization is insufficient.")
        if response.status_code >= 500:
            raise ToolFailure(ErrorCode.UPSTREAM_UNAVAILABLE, "The operations API is unavailable.")
