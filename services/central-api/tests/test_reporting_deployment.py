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


def _service_blocks(compose_text: str) -> dict[str, str]:
    """Every top-level service block, so audits derive their own subject list."""
    body = compose_text.split("\nservices:\n", 1)[1]
    return {
        match.group("name"): match.group(0)
        for match in re.finditer(
            r"^  (?P<name>[a-z0-9-]+):\n(?:    .*\n|\n)*", body, re.MULTILINE
        )
    }


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
    postgres_dockerfile = (REPO_ROOT / "docker/prefect-postgres.Dockerfile").read_text()
    assert postgres_dockerfile.startswith("FROM postgres:16@sha256:")
    assert "COPY --chmod=0444 docker/prefect-postgres-init.sql" in postgres_dockerfile
    assert "COPY --chmod=0555 docker/prefect-postgres-backup-role.sh" in postgres_dockerfile

    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        postgres = _service_block(compose_text, "prefect-postgres")
        bootstrap = _service_block(compose_text, "prefect-postgres-bootstrap")
        server = _service_block(compose_text, "prefect-server")
        backup = _service_block(compose_text, "prefect-db-backup")
        reporting = _service_block(compose_text, "reporting-worker")
        maintenance = _service_block(compose_text, "maintenance-worker")

        assert "dockerfile: docker/prefect-postgres.Dockerfile" in postgres
        assert "./docker/prefect-postgres-init.sql:" not in compose_text
        assert "./docker/prefect-postgres-backup-role.sh:" not in compose_text
        assert "pg_isready -U prefect -d prefect" in postgres
        assert "pg_extension" not in postgres
        assert "prefect-postgres: {condition: service_healthy}" in bootstrap
        assert 'command: ["/usr/local/bin/prefect-postgres-bootstrap"]' in bootstrap
        assert "prefect-postgres-bootstrap: {condition: service_completed_successfully}" in server
        assert "prefect-postgres-bootstrap: {condition: service_completed_successfully}" in backup
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


def test_prefect_database_bootstrap_repairs_existing_volumes_idempotently() -> None:
    script = (REPO_ROOT / "docker/prefect-postgres-bootstrap.sh").read_text()
    assert "set -eu" in script
    assert "--set=ON_ERROR_STOP=1" in script
    assert "10-pg-trgm.sql" in script
    assert "20-backup-role.sh" in script
    assert "prefect_postgres_bootstrap=complete" in script


def test_central_api_container_health_uses_liveness_not_dependency_readiness() -> None:
    dockerfile = (REPO_ROOT / "docker/central-api.Dockerfile").read_text()
    healthcheck = next(line for line in dockerfile.splitlines() if line.startswith("HEALTHCHECK"))
    assert "/health/live" in healthcheck
    assert "/health/ready" not in healthcheck


def test_prefect_postgres_guard_rejects_sqlite_fallback() -> None:
    guard_script = (REPO_ROOT / "docker/prefect-postgres-guard.sh").read_text()
    assert "tablename='flow_run'" in guard_script
    assert "extname='pg_trgm'" in guard_script
    # prefect-server reports healthy as soon as its API binds, before its
    # first-boot migration necessarily created flow_run. A single-shot check
    # races that window; the loop must be bounded so it cannot hang instead.
    assert "PREFECT_GUARD_TIMEOUT_SECONDS" in guard_script
    assert "prefect_postgres_guard=complete" in guard_script
    assert "prefect_postgres_guard=failed reason=" in guard_script

    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        guard = _service_block(compose_text, "prefect-postgres-guard")
        version_guard = _service_block(compose_text, "prefect-version-guard")
        assert "/usr/local/bin/prefect-postgres-guard" in guard
        assert 'profiles: ["verification"]' not in guard
        assert "scripts.prefect_version_guard" in version_guard


def test_guards_do_not_gate_deployment_startup() -> None:
    """`up -d` must not stay attached waiting for the one-shot guards.

    Compose blocks until every `service_completed_successfully` dependency exits.
    Gating reporting-worker on the guards charged them to Coolify's command
    boundary, where the command was killed as exit 255 and cleanup removed the
    containers. The version guard is a static check and must not wait on a server
    it never contacts.
    """
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        reporting = _service_block(compose_text, "reporting-worker")
        version_guard = _service_block(compose_text, "prefect-version-guard")
        assert "prefect-postgres-guard: {condition: service_completed_successfully}" not in reporting
        assert "prefect-version-guard: {condition: service_completed_successfully}" not in reporting
        assert "prefect-server: {condition: service_healthy}" not in version_guard


def test_reporting_worker_enforces_guard_conditions_fail_closed() -> None:
    """What Compose no longer gates, the worker must enforce itself."""
    worker = (REPO_ROOT / "data/pipelines/business_performance/worker.py").read_text()
    assert "verify_startup_contract()" in worker
    assert "reporting_worker_startup_guard=failed" in worker
    assert "SystemExit(1)" in worker

    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        reporting = _service_block(compose_text, "reporting-worker")
        # Least privilege: a CONNECT-only role that cannot read Prefect state, not
        # the backup role, which holds SELECT ON ALL TABLES.
        assert "PREFECT_GUARD_DB_USER: prefect_guard" in reporting
        assert "prefect_backup" not in reporting
        # Discrete parts, never an interpolated DSN: a password may contain @ : / + =.
        assert "PREFECT_GUARD_DATABASE_URL" not in compose_text
        assert "restart: on-failure" in reporting


def test_guard_role_is_connect_only_and_separate_from_the_backup_role() -> None:
    """The guard credential lives in a long-running worker; it must read nothing."""
    guard_role = (REPO_ROOT / "docker/prefect-postgres-guard-role.sh").read_text()
    assert "GRANT CONNECT ON DATABASE prefect TO prefect_guard;" in guard_role
    # pg_catalog is readable by PUBLIC, so the guard needs no table or schema grants.
    assert "GRANT SELECT" not in guard_role
    assert "GRANT USAGE" not in guard_role

    # Bootstrap must repair the role on already-initialized volumes, like the others.
    bootstrap = (REPO_ROOT / "docker/prefect-postgres-bootstrap.sh").read_text()
    assert "30-guard-role.sh" in bootstrap
    assert 'PREFECT_GUARD_DB_PASSWORD:?required' in bootstrap
    assert "docker/prefect-postgres-guard-role.sh" in (REPO_ROOT / "docker/prefect-postgres.Dockerfile").read_text()


def test_non_http_central_api_services_disable_inherited_healthcheck() -> None:
    """The Central API image bakes a :8000 healthcheck non-HTTP commands never bind.

    Any such service is permanently unhealthy, which can make Coolify mark a
    deployment unhealthy after Compose already succeeded. Derived from the Compose
    files rather than listed, so a new worker or one-shot cannot reintroduce this.
    """
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        offenders = []
        for name, block in _service_blocks(compose_text).items():
            uses_image = "central-api.Dockerfile" in block or "trackflow-central-api" in block
            # Overriding `command` means the image's uvicorn CMD never runs, so
            # nothing binds :8000. Services without an override still serve HTTP.
            if not uses_image or "command:" not in block:
                continue
            if "healthcheck: {disable: true}" not in block:
                offenders.append(name)
        assert offenders == [], f"{filename}: non-HTTP services inherit the :8000 healthcheck: {offenders}"
