"""Static deployment boundaries for the reporting pipeline."""

import re
from pathlib import Path

from central_api.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]
R2_VARIABLES = (
    "REPORTING_R2_BUCKET",
    "REPORTING_R2_ENDPOINT",
    "REPORTING_R2_ACCESS_KEY_ID",
    "REPORTING_R2_SECRET_ACCESS_KEY",
)
BACKUP_R2_VARIABLES = (
    "PREFECT_BACKUP_R2_BUCKET",
    "PREFECT_BACKUP_R2_ENDPOINT",
    "PREFECT_BACKUP_R2_ACCESS_KEY_ID",
    "PREFECT_BACKUP_R2_SECRET_ACCESS_KEY",
)
PREFECT_IMAGE_DIGEST = "sha256:d4d142f1426ed0e8d7f48b3cc730f7b0469dcbcaf720959bb678f4cec3e5c3cc"


def _service_block(compose_text: str, service: str) -> str:
    match = re.search(rf"^  {re.escape(service)}:\n(?P<body>(?:    .*\n|\n)*)", compose_text, re.MULTILINE)
    assert match is not None
    return match.group(0)


def test_r2_secrets_are_scoped_to_reporting_worker_only() -> None:
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        worker = _service_block(compose_text, "reporting-worker")
        for variable in R2_VARIABLES:
            assert compose_text.count(variable) == 2  # environment key + interpolation
            assert worker.count(variable) == 2


def test_central_api_settings_have_no_r2_fields() -> None:
    assert not any(name.startswith("reporting_r2_") for name in Settings.model_fields)


def test_backup_credentials_are_scoped_to_the_backup_service() -> None:
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        backup = _service_block(compose_text, "prefect-db-backup")
        reporting = _service_block(compose_text, "reporting-worker")
        maintenance = _service_block(compose_text, "maintenance-worker")
        for variable in BACKUP_R2_VARIABLES:
            assert compose_text.count(variable) == 2
            assert backup.count(variable) == 2
            assert variable not in reporting
            assert variable not in maintenance
        assert "PGUSER: prefect_backup" in backup
        assert "\n      PGUSER: prefect\n" not in backup

    dockerfile = (REPO_ROOT / "docker/prefect-db-backup.Dockerfile").read_text()
    assert dockerfile.startswith("FROM postgres:16@sha256:")
    assert "boto3==" in dockerfile


def test_central_api_image_includes_the_data_project() -> None:
    dockerfile = (REPO_ROOT / "docker/central-api.Dockerfile").read_text()
    assert "COPY data data" in dockerfile


def test_dedicated_prefect_services_are_private_pinned_and_postgres_backed() -> None:
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        postgres = _service_block(compose_text, "prefect-postgres")
        server = _service_block(compose_text, "prefect-server")
        reporting = _service_block(compose_text, "reporting-worker")
        maintenance = _service_block(compose_text, "maintenance-worker")

        assert "postgres:16@sha256:" in postgres
        assert "PREFECT_API_DATABASE_CONNECTION_URL:" in server
        assert "postgresql+asyncpg://prefect:" in server
        assert "ports:" not in postgres
        assert "ports:" not in server
        assert "PREFECT_API_URL: http://prefect-server:4200/api" in reporting
        assert "PREFECT_API_URL: http://prefect-server:4200/api" in maintenance
        assert "prefect-server: {condition: service_healthy}" in reporting
        assert "prefect-server: {condition: service_healthy}" not in maintenance

    env_example = (REPO_ROOT / ".env.example").read_text()
    assert PREFECT_IMAGE_DIGEST in env_example


def test_prefect_postgres_guard_rejects_sqlite_fallback() -> None:
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        guard = _service_block(compose_text, "prefect-postgres-guard")
        version_guard = _service_block(compose_text, "prefect-version-guard")
        reporting = _service_block(compose_text, "reporting-worker")
        assert 'tablename=\'flow_run\'' in guard
        assert "extname='pg_trgm'" in guard
        assert 'profiles: ["verification"]' not in guard
        assert "scripts.prefect_version_guard" in version_guard
        assert "prefect-postgres-guard: {condition: service_completed_successfully}" in reporting
        assert "prefect-version-guard: {condition: service_completed_successfully}" in reporting
