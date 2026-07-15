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


def _service_block(compose_text: str, service: str) -> str:
    match = re.search(rf"^  {re.escape(service)}:\n(?P<body>(?:    .*\n|\n)*)", compose_text, re.MULTILINE)
    assert match is not None
    return match.group(0)


def test_r2_secrets_are_scoped_to_reporting_runner_only() -> None:
    for filename in ("compose.yaml", "compose.coolify.yaml"):
        compose_text = (REPO_ROOT / filename).read_text()
        runner = _service_block(compose_text, "reporting-runner")
        for variable in R2_VARIABLES:
            assert compose_text.count(variable) == 2  # environment key + interpolation
            assert runner.count(variable) == 2


def test_central_api_settings_have_no_r2_fields() -> None:
    assert not any(name.startswith("reporting_r2_") for name in Settings.model_fields)


def test_central_api_image_includes_the_data_project() -> None:
    dockerfile = (REPO_ROOT / "docker/central-api.Dockerfile").read_text()
    assert "COPY data data" in dockerfile
