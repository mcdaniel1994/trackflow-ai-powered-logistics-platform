"""Static deployment boundaries for the reporting pipeline."""

import re
from pathlib import Path

from central_api.core.config import Settings

REPO_ROOT = Path(__file__).resolve().parents[3]


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


def test_central_api_settings_have_no_r2_fields() -> None:
    assert not any(name.startswith("reporting_r2_") for name in Settings.model_fields)


def test_central_api_image_includes_rag_runtime_inputs() -> None:
    dockerfile = (REPO_ROOT / "docker/central-api.Dockerfile").read_text()
    dockerignore = (REPO_ROOT / ".dockerignore").read_text()
    assert "COPY data data" in dockerfile
    assert "COPY docs/company-knowledge-base docs/company-knowledge-base" in dockerfile
    assert "!docs/company-knowledge-base/" in dockerignore
    assert "!docs/company-knowledge-base/*.md" in dockerignore


def test_central_api_container_health_uses_liveness_not_dependency_readiness() -> None:
    dockerfile = (REPO_ROOT / "docker/central-api.Dockerfile").read_text()
    healthcheck = next(line for line in dockerfile.splitlines() if line.startswith("HEALTHCHECK"))
    assert "/health/live" in healthcheck
    assert "/health/ready" not in healthcheck


def test_reporting_logs_persist_with_bounded_non_root_access() -> None:
    dockerfile = (REPO_ROOT / "docker/central-api.Dockerfile").read_text()
    assert "install -d -o trackflow -g trackflow -m 0750 /var/log/trackflow/reporting" in dockerfile
    assert "USER 10001" in dockerfile

    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        reporting = _service_block(compose_text, "reporting-worker")
        maintenance = _service_block(compose_text, "maintenance-worker")

        assert "reporting-logs:" in compose_text.split("\nvolumes:\n", 1)[1]
        assert "reporting-logs:/var/log/trackflow/reporting" in reporting
        assert "reporting-logs:/var/log/trackflow/reporting" in maintenance
        assert "REPORTING_LOG_PATH: /var/log/trackflow/reporting/reporting-worker.log" in reporting
        assert 'REPORTING_LOG_MAX_BYTES: "10485760"' in reporting
        assert 'REPORTING_LOG_BACKUP_COUNT: "9"' in reporting
        assert (
            "REPORTING_HOURLY_ROLLUPS_ENABLED: "
            "${REPORTING_HOURLY_ROLLUPS_ENABLED:-false}"
        ) in reporting
        assert "REPORTING_LOG_PATH: /var/log/trackflow/reporting/reporting-worker.log" in maintenance
        assert 'REPORTING_LOG_RETENTION_DAYS: "14"' in maintenance
        assert 'REPORTING_LOG_TOTAL_BYTES: "262144000"' in maintenance


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


def test_no_prefect_surface_remains_in_deployment() -> None:
    """Prefect was retired in August 2026; nothing may quietly reintroduce it.

    See docs/archive/prefect-orchestration-retirement.md.
    """
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        assert "prefect" not in compose_text.lower()
    assert not list((REPO_ROOT / "docker").glob("prefect-*"))
