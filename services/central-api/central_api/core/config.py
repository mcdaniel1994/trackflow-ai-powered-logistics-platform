"""Environment-driven Central API configuration."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from trackflow_auth import TokenVerifierConfig  # type: ignore[import-untyped]

SERVICE_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Validate runtime settings once before they reach infrastructure code."""

    model_config = SettingsConfigDict(env_file=SERVICE_ROOT / ".env", extra="ignore", validate_default=True)

    database_url: str = ""
    migration_database_url: str | None = None
    database_connect_timeout_seconds: int = 10
    database_statement_timeout_ms: int = 15_000
    database_lock_timeout_ms: int = 5_000
    central_api_cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    app_env: str = "local"
    runtime_database_role: str = "trackflow_runtime"
    telemetry_enabled: bool = False
    telemetry_operational_retention_days: int = 90
    telemetry_security_retention_days: int = 365
    # Live operations feed (portfolio synthetic-but-canonical data generation).
    operations_feed_enabled: bool = False
    operations_feed_interval_seconds: float = 5.0
    operations_feed_batch_min: int = 1
    operations_feed_batch_max: int = 4
    operations_feed_backfill_days: int = 10
    operations_feed_user_uuid: str | None = None
    operations_feed_lock_key: int = 4306160006  # constant pg advisory-lock key for single-writer
    # Automatic database-size guardrails for the Supabase Free tier (500 MB cap).
    db_size_soft_limit_mb: int = 400
    db_size_hard_limit_mb: int = 450
    business_event_retention_weeks: int = 26
    identity_jwt_public_key: str = ""
    identity_jwt_algorithm: str = "RS256"
    identity_jwt_issuer: str = "trackflow-identity"
    identity_jwt_audience: str = "trackflow-backoffice"
    seed_user_uuid: str | None = None

    @field_validator("database_url")
    @classmethod
    def require_database_url(cls, value: str) -> str:
        """Fail fast instead of silently connecting to an unintended database."""
        if not value.strip():
            raise ValueError("DATABASE_URL is required")
        return value.strip()

    @property
    def alembic_database_url(self) -> str:
        """Use the dedicated DDL role when configured; local dev falls back safely."""
        if self.app_env.strip().lower() == "production" and not self.migration_database_url:
            raise ValueError("MIGRATION_DATABASE_URL is required when APP_ENV=production")
        return (self.migration_database_url or self.database_url).strip()

    @field_validator("identity_jwt_algorithm")
    @classmethod
    def require_rs256(cls, value: str) -> str:
        """Prevent configuration from weakening the Identity token algorithm."""
        if value.strip() != "RS256":
            raise ValueError("IDENTITY_JWT_ALGORITHM must be RS256")
        return "RS256"

    @property
    def cors_origins(self) -> list[str]:
        """Turn the environment-friendly comma list into a strict origin allowlist."""
        return [origin.strip() for origin in self.central_api_cors_origins.split(",") if origin.strip()]

    @property
    def auth_config(self) -> TokenVerifierConfig:
        """Adapt service settings to the shared verify-only auth package."""
        return TokenVerifierConfig(
            public_key=self.identity_jwt_public_key.replace("\\n", "\n").strip(),
            algorithm=self.identity_jwt_algorithm,
            issuer=self.identity_jwt_issuer,
            audience=self.identity_jwt_audience,
        )


@lru_cache
def get_settings() -> Settings:
    """Reuse immutable process configuration without creating mutable request state."""
    return Settings()
