"""Release workflow ordering and rollback-condition contract."""

from pathlib import Path


def test_release_orders_migration_deploy_readiness_and_rollback() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/deploy-production.yml").read_text()
    migration = workflow.index("name: Run and verify production migrations")
    deploy = workflow.index("name: Deploy immutable SHA through Coolify")
    readiness = workflow.index("name: Poll application health and unauthenticated protection")
    rollback = workflow.index("name: Restore previous image after deployment or health failure")
    assert migration < deploy < readiness < rollback
    assert "steps.coolify_deploy.outcome == 'failure' || steps.release_verification.outcome == 'failure'" in workflow
    assert 'TARGET_IMAGE_TAG="$PREVIOUS_IMAGE_TAG"' in workflow
    assert "CAPTURE_PREVIOUS_IMAGE_TAG=false" in workflow
    assert "if: env.DEPLOYMENT_MODE == 'release'" in workflow
    assert 'echo "Image rollback:' in workflow
