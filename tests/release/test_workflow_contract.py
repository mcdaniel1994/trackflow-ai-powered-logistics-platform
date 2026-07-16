"""Release workflow ordering and rollback-condition contract."""

from pathlib import Path


def test_release_orders_migration_deploy_readiness_and_rollback() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/deploy-production.yml").read_text()
    prefect_contract = workflow.index("name: Validate Prefect release contract")
    migration = workflow.index("name: Run and verify production migrations")
    deploy = workflow.index("name: Deploy immutable SHA through Coolify")
    readiness = workflow.index("name: Poll application health and unauthenticated protection")
    rollback = workflow.index("name: Restore previous image after deployment or health failure")
    assert prefect_contract < migration < deploy < readiness < rollback
    assert "steps.coolify_deploy.outcome == 'failure' || steps.release_verification.outcome == 'failure'" in workflow
    assert 'TARGET_IMAGE_TAG="$PREVIOUS_IMAGE_TAG"' in workflow
    assert "CAPTURE_PREVIOUS_IMAGE_TAG=false" in workflow
    assert "if: env.DEPLOYMENT_MODE == 'release'" in workflow
    assert 'echo "Image rollback:' in workflow
    assert 'echo "Prefect guards:' in workflow


def test_prefect_release_contract_is_static_and_live_guarded() -> None:
    root = Path(__file__).resolve().parents[2]
    script = (root / "scripts/release/verify_prefect_contract.py").read_text()
    compose = (root / "compose.coolify.yaml").read_text()
    assert "data/uv.lock" in script
    assert "PREFECT_SERVER_IMAGE" in script
    assert "prefect-postgres-bootstrap: {condition: service_completed_successfully}" in compose
    assert "prefect-postgres-guard: {condition: service_completed_successfully}" in compose
    assert "prefect-version-guard: {condition: service_completed_successfully}" in compose
    assert "./docker/prefect-postgres-init.sql:" not in compose
    assert "./docker/prefect-postgres-backup-role.sh:" not in compose
