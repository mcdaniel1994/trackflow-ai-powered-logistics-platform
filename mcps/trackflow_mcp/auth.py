"""mcpauth configuration and TrackFlow Identity JWT verification."""

from __future__ import annotations

from typing import Any

import jwt
from mcpauth import AuthInfo, MCPAuth, ResourceServerConfig
from mcpauth.config import AuthorizationServerMetadata, AuthServerConfig, AuthServerType
from mcpauth.exceptions import MCPAuthTokenVerificationException, MCPAuthTokenVerificationExceptionCode
from mcpauth.types import ResourceServerMetadata

from .config import MCPSettings

SCOPES = ["mcp:connect", "incidents:read", "incidents:write", "inventory:read"]


def build_auth(settings: MCPSettings) -> MCPAuth:
    authorization_server = AuthServerConfig(
        type=AuthServerType.OAUTH,
        metadata=AuthorizationServerMetadata(
            issuer=settings.identity_oauth_issuer_url,
            authorization_endpoint=f"{settings.identity_oauth_issuer_url}/oauth/authorize",
            token_endpoint=settings.oauth_token_url,
            jwks_uri=settings.oauth_jwks_url,
            registration_endpoint=f"{settings.identity_oauth_issuer_url}/oauth/register",
            scopes_supported=SCOPES,
            response_types_supported=["code"],
            grant_types_supported=[
                "authorization_code",
                "client_credentials",
                "urn:ietf:params:oauth:grant-type:token-exchange",
            ],
            token_endpoint_auth_methods_supported=["none", "client_secret_basic", "client_secret_post"],
            code_challenge_methods_supported=["S256"],
        ),
    )
    return MCPAuth(
        protected_resources=ResourceServerConfig(
            metadata=ResourceServerMetadata(
                resource=settings.mcp_resource_url,
                resource_name="TrackFlow operations tools",
                scopes_supported=SCOPES,
                bearer_methods_supported=["header"],
                authorization_servers=[authorization_server],
            )
        )
    )


def build_token_verifier(settings: MCPSettings):  # type: ignore[no-untyped-def]
    def verify(token: str) -> AuthInfo:
        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                settings.identity_jwt_public_key,
                algorithms=["RS256"],
                audience=settings.mcp_resource_url,
                issuer=settings.identity_oauth_issuer_url,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "client_id", "scope", "jti"]},
            )
        except jwt.PyJWTError as exc:
            raise MCPAuthTokenVerificationException(
                MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN
            ) from exc
        if claims.get("token_type") != "access" or claims.get("status", "active") != "active":
            raise MCPAuthTokenVerificationException(MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN)
        scope = claims.get("scope")
        if not isinstance(scope, str):
            raise MCPAuthTokenVerificationException(MCPAuthTokenVerificationExceptionCode.INVALID_TOKEN)
        return AuthInfo(
            token=token,
            issuer=str(claims["iss"]),
            client_id=str(claims["client_id"]),
            scopes=[value for value in scope.split(" ") if value],
            subject=str(claims["sub"]),
            audience=claims["aud"],
            claims=claims,
        )

    return verify
