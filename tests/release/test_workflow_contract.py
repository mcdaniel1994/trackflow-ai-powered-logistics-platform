"""Release workflow ordering and rollback-condition contract."""

from pathlib import Path


def test_release_orders_migration_deploy_readiness_and_rollback() -> None:
    workflow = (Path(__file__).resolve().parents[2] / ".github/workflows/deploy-production.yml").read_text()
    prefect_contract = workflow.index("name: Validate Prefect release contract")
    migration = workflow.index("name: Run and verify production migrations")
    deploy = workflow.index("name: Deploy immutable SHA through Coolify")
    readiness = workflow.index("name: Poll application health and unauthenticated protection")
    guard_verification = workflow.index("name: Verify Prefect startup guards from live worker state")
    rollback = workflow.index("name: Restore previous image after deployment or health failure")
    assert prefect_contract < migration < deploy < readiness < guard_verification < rollback
    assert "steps.coolify_deploy.outcome == 'failure' || steps.release_verification.outcome == 'failure'" in workflow
    # A guard rejection must roll the release back, not just be reported.
    assert "steps.prefect_guard_verification.outcome == 'failure'" in workflow
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
    assert "./docker/prefect-postgres-init.sql:" not in compose
    assert "./docker/prefect-postgres-backup-role.sh:" not in compose
    # The one-shot guards must stay off the deploy critical path: `up -d` blocks
    # until a `service_completed_successfully` dependency exits, which is what
    # made the failed deployment end as an opaque exit 255.
    assert "prefect-postgres-guard: {condition: service_completed_successfully}" not in compose
    assert "prefect-version-guard: {condition: service_completed_successfully}" not in compose


def test_release_measures_prefect_guard_outcome_rather_than_asserting_it() -> None:
    """The guard result must come from live worker state, not a hard-coded echo."""
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
    guard_check = workflow.index("name: Verify Prefect startup guards from live worker state")
    # The boundary must be recorded after Coolify returns and before it is used.
    assert deploy < boundary_step < guard_check
    assert "REPORTING_STARTUP_MIN_HEARTBEAT_AT" in workflow
    assert "worker_heartbeat_predates_deployment" in verifier
    assert 'worker["heartbeat_at"] < boundary' in verifier
