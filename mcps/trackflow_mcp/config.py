"""Environment-only configuration for the TrackFlow MCP resource server."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPSettings(BaseSettings):
    """Validated MCP, Identity, and Central API connection settings."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    app_environment: str = "local"
    identity_oauth_issuer_url: str = "http://localhost:8002"
    identity_oauth_internal_url: str = "http://localhost:8002"
    identity_jwt_public_key: str = ""
    oauth_client_id: str = ""
    oauth_client_secret: SecretStr = SecretStr("")
    mcp_resource_url: str = "http://localhost:8004/mcp"
    central_api_url: str = "http://localhost:8003"
    central_api_oauth_resource_url: str = "http://localhost:8003"
    upstream_connect_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    upstream_read_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    @field_validator("identity_jwt_public_key", mode="before")
    @classmethod
    def expand_pem_newlines(cls, value: object) -> object:
        return value.replace("\\n", "\n") if isinstance(value, str) else value

    @field_validator(
        "identity_oauth_issuer_url",
        "identity_oauth_internal_url",
        "mcp_resource_url",
        "central_api_url",
        "central_api_oauth_resource_url",
    )
    @classmethod
    def normalize_url(cls, value: str) -> str:
        return value.strip().rstrip("/")

    @model_validator(mode="after")
    def require_secure_hosted_urls(self) -> MCPSettings:
        public_urls = (
            self.identity_oauth_issuer_url,
            self.mcp_resource_url,
            self.central_api_oauth_resource_url,
        )
        for value in public_urls:
            parsed = urlparse(value)
            local = parsed.hostname in {"localhost", "127.0.0.1"}
            if (
                not parsed.netloc
                or parsed.query
                or parsed.fragment
                or parsed.scheme not in {"http", "https"}
                or (
                    parsed.scheme != "https"
                    and not (local and self.app_environment != "production")
                )
            ):
                raise ValueError("Public OAuth URLs must use HTTPS except on loopback hosts")
        for value in (self.identity_oauth_internal_url, self.central_api_url):
            parsed = urlparse(value)
            if not parsed.netloc or parsed.query or parsed.fragment or parsed.scheme not in {"http", "https"}:
                raise ValueError("Internal service URLs must be absolute HTTP(S) URLs")
        if self.app_environment == "production" and (
            not self.oauth_client_id
            or not self.oauth_client_secret.get_secret_value()
            or not self.identity_jwt_public_key
        ):
            raise ValueError("Production MCP OAuth credentials and the Identity public key are required")
        return self

    @property
    def oauth_token_url(self) -> str:
        return f"{self.identity_oauth_internal_url}/oauth/token"

    @property
    def oauth_jwks_url(self) -> str:
        return f"{self.identity_oauth_issuer_url}/oauth/jwks.json"


@lru_cache
def get_settings() -> MCPSettings:
    return MCPSettings()
