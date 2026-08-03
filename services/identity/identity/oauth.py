"""OAuth 2.1 authorization-server workflows owned by TrackFlow Identity."""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlparse

from jose import JWTError, jwt

from .config import IdentitySettings
from .constants import STATUS_ACTIVE
from .repository import OAuthClientRepository, OAuthCodeRepository, UserRepository
from .security import (
    hash_oauth_token,
    hash_password,
    now_utc,
    sign_oauth_access_token,
    verify_password,
)

LOGGER = logging.getLogger(__name__)

MCP_CONNECT_SCOPE = "mcp:connect"
INCIDENTS_READ_SCOPE = "incidents:read"
INCIDENTS_WRITE_SCOPE = "incidents:write"
INVENTORY_READ_SCOPE = "inventory:read"
SUPPORTED_SCOPES = frozenset(
    {
        MCP_CONNECT_SCOPE,
        INCIDENTS_READ_SCOPE,
        INCIDENTS_WRITE_SCOPE,
        INVENTORY_READ_SCOPE,
    }
)
TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
ACCESS_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:access_token"
PKCE_VALUE = re.compile(r"^[A-Za-z0-9._~-]{43,128}$")
PKCE_CHALLENGE = re.compile(r"^[A-Za-z0-9_-]{43,128}$")


def _audit(*, client_id: str, subject: str, grant: str, outcome: str) -> None:
    LOGGER.info(
        "oauth.audit client_id=%s subject=%s grant=%s outcome=%s timestamp=%s",
        client_id,
        subject,
        grant,
        outcome,
        now_utc().isoformat(),
    )


@dataclass(frozen=True)
class OAuthError(Exception):
    """Safe OAuth protocol error translated by the route layer."""

    error: str
    description: str
    status_code: int = 400


@dataclass(frozen=True)
class OAuthToken:
    access_token: str
    expires_in: int
    scope: str


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return []
    return [str(item) for item in value]


def _scopes(value: str) -> frozenset[str]:
    return frozenset(part for part in value.split(" ") if part)


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


class OAuthService:
    """Coordinates registered clients, user consent, codes, and resource tokens."""

    def __init__(
        self,
        users: UserRepository,
        clients: OAuthClientRepository,
        codes: OAuthCodeRepository,
        settings: IdentitySettings,
    ) -> None:
        self.users = users
        self.clients = clients
        self.codes = codes
        self.settings = settings

    def metadata(self) -> dict[str, object]:
        issuer = self.settings.oauth_issuer_url
        return {
            "issuer": issuer,
            "authorization_endpoint": f"{issuer}/oauth/authorize",
            "token_endpoint": f"{issuer}/oauth/token",
            "jwks_uri": f"{issuer}/oauth/jwks.json",
            "registration_endpoint": f"{issuer}/oauth/register",
            "response_types_supported": ["code"],
            "grant_types_supported": [
                "authorization_code",
                "client_credentials",
                TOKEN_EXCHANGE_GRANT,
            ],
            "token_endpoint_auth_methods_supported": [
                "none",
                "client_secret_basic",
                "client_secret_post",
            ],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": sorted(SUPPORTED_SCOPES),
        }

    def register_public_client(
        self,
        *,
        client_name: str,
        redirect_uris: list[str],
        scopes: frozenset[str],
        resources: list[str],
    ) -> dict[str, object]:
        if not self.settings.oauth_dynamic_registration_enabled:
            raise OAuthError(
                "registration_not_supported",
                "Dynamic client registration is disabled.",
                403,
            )
        if not client_name.strip() or len(client_name) > 160:
            raise OAuthError(
                "invalid_client_metadata", "A valid client name is required."
            )
        self._validate_redirect_uris(redirect_uris)
        self._validate_scopes(scopes)
        self._validate_resources(resources)
        record = self.clients.create(
            {
                "client_name": client_name,
                "client_secret_hash": None,
                "redirect_uris": redirect_uris,
                "grant_types": ["authorization_code"],
                "scopes": sorted(scopes),
                "resources": resources,
                "source_audiences": [],
                "token_endpoint_auth_method": "none",
            }
        )
        LOGGER.info(
            "oauth.client.registered client_id=%s client_type=public",
            record["client_id"],
        )
        return record

    def register_confidential_client(
        self,
        *,
        client_name: str,
        grants: frozenset[str],
        scopes: frozenset[str],
        resources: list[str],
        source_audiences: list[str],
    ) -> tuple[str, str]:
        self._validate_scopes(scopes)
        self._validate_resources(resources)
        allowed_grants = {"client_credentials", TOKEN_EXCHANGE_GRANT}
        if not grants or not grants.issubset(allowed_grants):
            raise OAuthError(
                "invalid_client_metadata", "Unsupported confidential-client grant type."
            )
        client_secret = secrets.token_urlsafe(48)
        record = self.clients.create(
            {
                "client_name": client_name,
                "client_secret_hash": hash_password(client_secret),
                "redirect_uris": [],
                "grant_types": sorted(grants),
                "scopes": sorted(scopes),
                "resources": resources,
                "source_audiences": source_audiences,
                "token_endpoint_auth_method": "client_secret_basic",
            }
        )
        return str(record["client_id"]), client_secret

    def validate_authorization_request(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        response_type: str,
        scope: str,
        resource: str,
        code_challenge: str,
        code_challenge_method: str,
    ) -> dict[str, object]:
        client = self.validate_redirect_uri(client_id, redirect_uri)
        if response_type != "code" or "authorization_code" not in _string_list(
            client.get("grant_types")
        ):
            raise OAuthError(
                "unsupported_response_type",
                "Only the authorization code flow is supported.",
            )
        requested = _scopes(scope)
        self._require_client_scopes(client, requested)
        self._require_client_resource(client, resource)
        if code_challenge_method != "S256" or not PKCE_CHALLENGE.fullmatch(
            code_challenge
        ):
            raise OAuthError("invalid_request", "S256 PKCE is required.")
        return client

    def validate_redirect_uri(
        self, client_id: str, redirect_uri: str
    ) -> dict[str, object]:
        """Return the active client only for an exact registered redirect URI."""
        client = self._active_client(client_id)
        if redirect_uri not in _string_list(client.get("redirect_uris")):
            raise OAuthError("invalid_request", "The redirect URI is not registered.")
        return client

    def authorize(
        self,
        *,
        email: str,
        password: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        resource: str,
        code_challenge: str,
    ) -> str:
        self.validate_authorization_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type="code",
            scope=scope,
            resource=resource,
            code_challenge=code_challenge,
            code_challenge_method="S256",
        )
        user = self.users.get_by_email(email)
        if (
            not user
            or user.get("status") != STATUS_ACTIVE
            or user.get("must_change_password") is True
            or not verify_password(password, str(user.get("hashed_password", "")))
        ):
            _audit(
                client_id=client_id,
                subject="unknown",
                grant="authorization_code",
                outcome="denied",
            )
            raise OAuthError("access_denied", "Authorization was denied.", 401)

        code = secrets.token_urlsafe(48)
        self.codes.cleanup_expired()
        self.codes.create(
            {
                "token_hash": hash_oauth_token(code),
                "client_id": client_id,
                "user_id": str(user["id"]),
                "role": str(user["role"]),
                "jurisdiction": user.get("jurisdiction") if user.get("jurisdiction") in {"US", "ES"} else None,
                "redirect_uri": redirect_uri,
                "scope": scope,
                "resource": resource,
                "code_challenge": code_challenge,
                "expires_at": (
                    now_utc()
                    + timedelta(
                        minutes=self.settings.oauth_authorization_code_expire_minutes
                    )
                ).isoformat(),
            }
        )
        _audit(
            client_id=client_id,
            subject=str(user["id"]),
            grant="authorization_code",
            outcome="approved",
        )
        return code

    def exchange_authorization_code(
        self,
        *,
        client_id: str,
        client_secret: str | None,
        code: str,
        redirect_uri: str,
        code_verifier: str,
    ) -> OAuthToken:
        client = self._authenticate_client(
            client_id, client_secret, grant="authorization_code"
        )
        record = self.codes.consume(hash_oauth_token(code))
        if not record or str(record.get("expires_at", "")) <= now_utc().isoformat():
            raise OAuthError(
                "invalid_grant", "The authorization code is invalid or expired."
            )
        if (
            str(record.get("client_id")) != client_id
            or str(record.get("redirect_uri")) != redirect_uri
        ):
            raise OAuthError(
                "invalid_grant", "The authorization code is invalid or expired."
            )
        if not PKCE_VALUE.fullmatch(code_verifier) or not secrets.compare_digest(
            _pkce_challenge(code_verifier), str(record.get("code_challenge", ""))
        ):
            raise OAuthError("invalid_grant", "PKCE verification failed.")
        requested = _scopes(str(record.get("scope", "")))
        self._require_client_scopes(client, requested)
        issued = self._issue(
            subject=str(record["user_id"]),
            client_id=client_id,
            scopes=requested,
            audience=str(record["resource"]),
            role=str(record.get("role", "user")),
            jurisdiction=(
                str(record["jurisdiction"])
                if record.get("jurisdiction") in {"US", "ES"}
                else None
            ),
        )
        _audit(
            client_id=client_id,
            subject=str(record["user_id"]),
            grant="authorization_code",
            outcome="issued",
        )
        return issued

    def client_credentials(
        self,
        *,
        client_id: str,
        client_secret: str | None,
        scope: str,
        resource: str,
    ) -> OAuthToken:
        client = self._authenticate_client(
            client_id, client_secret, grant="client_credentials"
        )
        requested = _scopes(scope)
        self._require_client_scopes(client, requested)
        self._require_client_resource(client, resource)
        issued = self._issue(
            subject=f"client:{client_id}",
            client_id=client_id,
            scopes=requested,
            audience=resource,
        )
        _audit(
            client_id=client_id,
            subject=f"client:{client_id}",
            grant="client_credentials",
            outcome="issued",
        )
        return issued

    def token_exchange(
        self,
        *,
        client_id: str,
        client_secret: str | None,
        subject_token: str,
        scope: str,
        resource: str,
    ) -> OAuthToken:
        client = self._authenticate_client(
            client_id, client_secret, grant=TOKEN_EXCHANGE_GRANT
        )
        requested = _scopes(scope)
        self._require_client_scopes(client, requested)
        self._require_client_resource(client, resource)
        subject = self._verify_subject_token(subject_token, client)
        source_scopes_value = subject["scopes"]
        source_scopes = (
            source_scopes_value if isinstance(source_scopes_value, frozenset) else None
        )
        if source_scopes is not None and not requested.issubset(source_scopes):
            raise OAuthError("invalid_scope", "Token exchange may not increase scopes.")
        issued = self._issue(
            subject=str(subject["sub"]),
            client_id=client_id,
            scopes=requested,
            audience=resource,
            role=str(subject["role"]),
            actor=str(subject.get("client_id") or "trackflow-backoffice"),
            jurisdiction=str(subject["jurisdiction"])
            if subject.get("jurisdiction") in {"US", "ES"}
            else None,
        )
        _audit(
            client_id=client_id,
            subject=str(subject["sub"]),
            grant=TOKEN_EXCHANGE_GRANT,
            outcome="issued",
        )
        return issued

    def _issue(
        self,
        *,
        subject: str,
        client_id: str,
        scopes: frozenset[str],
        audience: str,
        role: str = "service",
        actor: str | None = None,
        jurisdiction: str | None = None,
    ) -> OAuthToken:
        token, expires_in = sign_oauth_access_token(
            subject=subject,
            client_id=client_id,
            scopes=scopes,
            audience=audience,
            settings=self.settings,
            role=role,
            actor=actor,
            jurisdiction=jurisdiction,
        )
        return OAuthToken(token, expires_in, " ".join(sorted(scopes)))

    def _active_client(self, client_id: str) -> dict[str, object]:
        client = self.clients.get(client_id)
        if not client or client.get("active") is not True:
            raise OAuthError("invalid_client", "Client authentication failed.", 401)
        return client

    def _authenticate_client(
        self, client_id: str, client_secret: str | None, *, grant: str
    ) -> dict[str, object]:
        client = self._active_client(client_id)
        if grant not in _string_list(client.get("grant_types")):
            raise OAuthError(
                "unauthorized_client", "The client may not use this grant type.", 403
            )
        secret_hash = client.get("client_secret_hash")
        if secret_hash is not None and (
            not client_secret or not verify_password(client_secret, str(secret_hash))
        ):
            raise OAuthError("invalid_client", "Client authentication failed.", 401)
        if secret_hash is None and client_secret:
            raise OAuthError("invalid_client", "Client authentication failed.", 401)
        return client

    def _verify_subject_token(
        self, token: str, client: dict[str, object]
    ) -> dict[str, object]:
        try:
            unverified = jwt.get_unverified_claims(token)
            audience = unverified.get("aud")
            if not isinstance(audience, str) or audience not in _string_list(
                client.get("source_audiences")
            ):
                raise OAuthError(
                    "invalid_grant", "The subject token audience is not allowed."
                )
            issuer = str(unverified.get("iss", ""))
            if issuer not in {self.settings.jwt_issuer, self.settings.oauth_issuer_url}:
                raise OAuthError(
                    "invalid_grant", "The subject token issuer is not allowed."
                )
            claims = jwt.decode(
                token,
                self.settings.jwt_public_key,
                algorithms=[self.settings.jwt_algorithm],
                issuer=issuer,
                audience=audience,
            )
        except OAuthError:
            raise
        except JWTError as exc:
            raise OAuthError(
                "invalid_grant", "The subject token is invalid or expired."
            ) from exc
        if (
            claims.get("token_type") != "access"
            or claims.get("status", "active") != "active"
            or claims.get("must_change_password") is True
        ):
            raise OAuthError(
                "invalid_grant", "The subject token is invalid or expired."
            )
        source_scope = claims.get("scope")
        return {
            "sub": str(claims["sub"]),
            "role": str(claims.get("role", "service")),
            "client_id": claims.get("client_id"),
            "jurisdiction": claims.get("jurisdiction"),
            "scopes": _scopes(source_scope) if isinstance(source_scope, str) else None,
        }

    def _require_client_scopes(
        self, client: dict[str, object], requested: frozenset[str]
    ) -> None:
        self._validate_scopes(requested)
        if not requested.issubset(frozenset(_string_list(client.get("scopes")))):
            raise OAuthError(
                "invalid_scope", "One or more requested scopes are not allowed."
            )

    def _require_client_resource(
        self, client: dict[str, object], resource: str
    ) -> None:
        if resource not in _string_list(client.get("resources")):
            raise OAuthError("invalid_target", "The requested resource is not allowed.")

    def _validate_scopes(self, scopes: frozenset[str]) -> None:
        if not scopes or not scopes.issubset(SUPPORTED_SCOPES):
            raise OAuthError(
                "invalid_scope", "One or more requested scopes are not supported."
            )

    def _validate_redirect_uris(self, redirect_uris: list[str]) -> None:
        if not redirect_uris:
            raise OAuthError(
                "invalid_redirect_uri", "At least one redirect URI is required."
            )
        for uri in redirect_uris:
            parsed = urlparse(uri)
            local_http = (
                parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1"}
                and self.settings.app_environment != "production"
            )
            if (
                not parsed.netloc
                or parsed.fragment
                or (parsed.scheme != "https" and not local_http)
            ):
                raise OAuthError(
                    "invalid_redirect_uri",
                    "Redirect URIs must use HTTPS or local HTTP.",
                )

    def _validate_resources(self, resources: list[str]) -> None:
        if not resources:
            raise OAuthError(
                "invalid_client_metadata", "At least one resource URI is required."
            )
        for resource in resources:
            parsed = urlparse(resource)
            local_http = (
                parsed.scheme == "http"
                and parsed.hostname in {"localhost", "127.0.0.1"}
                and self.settings.app_environment != "production"
            )
            if not parsed.netloc or (parsed.scheme != "https" and not local_http):
                raise OAuthError(
                    "invalid_client_metadata",
                    "Resource URIs must use HTTPS or local HTTP.",
                )
