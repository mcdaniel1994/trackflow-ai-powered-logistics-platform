"""Release workflow ordering and rollback-condition contract."""

from pathlib import Path


def test_release_orders_migration_deploy_readiness_and_rollback() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/deploy-production.yml").read_text()
    compose_validation = workflow.index("name: Validate production compose file")
    migration = workflow.index("name: Run and verify production migrations")
    deploy = workflow.index("name: Deploy immutable SHA through Coolify")
    readiness = workflow.index("name: Poll application health and unauthenticated protection")
    guard_verification = workflow.index("name: Verify reporting separately from core readiness")
    rollback = workflow.index("name: Restore previous image after deployment or health failure")
    assert compose_validation < migration < deploy < readiness < guard_verification < rollback
    assert "steps.coolify_deploy.outcome == 'failure' || steps.release_verification.outcome == 'failure'" in workflow
    # Reporting is recorded separately and can never amplify into image rollback.
    rollback_condition = workflow[rollback : workflow.index("name: Fail an unsuccessful release")]
    assert "steps.reporting_verification.outcome" not in rollback_condition
    assert "/api/health/ready" in workflow
    assert "/api/health/reporting" in workflow
    assert 'TARGET_IMAGE_TAG="$PREVIOUS_IMAGE_TAG"' in workflow
    assert "CAPTURE_PREVIOUS_IMAGE_TAG=false" in workflow
    assert "if: env.DEPLOYMENT_MODE == 'release'" in workflow
    assert 'echo "Image rollback:' in workflow
    assert 'echo "Reporting verification (non-rollback):' in workflow
def test_release_measures_reporting_worker_outcome_rather_than_asserting_it() -> None:
    """Selected-executor startup must come from live worker state, not a hard-coded echo."""
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/deploy-production.yml").read_text()
    verifier = (root / "services/central-api/scripts/verify_reporting_startup.py").read_text()
    assert "scripts.verify_reporting_startup" in workflow
    assert "reporting_startup=verified" in verifier
    assert "worker_heartbeat_absent" in verifier
    assert "orchestrator_unhealthy" in verifier


def test_guard_verification_rejects_pre_deployment_heartbeats() -> None:
    """A heartbeat from the replaced worker must not pass verification.

    The previous worker heartbeats until Compose replaces it, so a freshness
    window alone would accept its final heartbeat as proof of the new one.
    """
    root = Path(__file__).resolve().parents[2]
    workflow = (root / ".github/workflows/deploy-production.yml").read_text()
    verifier = (root / "services/central-api/scripts/verify_reporting_startup.py").read_text()

    boundary_step = workflow.index("name: Record post-deployment verification boundary")
    deploy = workflow.index("name: Deploy immutable SHA through Coolify")
    guard_check = workflow.index("name: Verify reporting separately from core readiness")
    # The boundary must be recorded after Coolify returns and before it is used.
    assert deploy < boundary_step < guard_check
    assert "REPORTING_STARTUP_MIN_HEARTBEAT_AT" in workflow
    assert "worker_heartbeat_predates_deployment" in verifier
    assert 'worker["heartbeat_at"] < boundary' in verifier
