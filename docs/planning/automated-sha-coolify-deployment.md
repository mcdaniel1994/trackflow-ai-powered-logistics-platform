# Automated SHA Deployment to Coolify

## Summary

Extend the existing GHCR workflow so every eligible `main` commit:

1. Passes release checks.
2. Publishes all three immutable `sha-<commit>` images.
3. Waits for GitHub Production approval.
4. Updates only Coolify's `TRACKFLOW_IMAGE_TAG`.
5. Deploys and verifies that exact SHA.

Normal deployments require no copying. Rollbacks use a GitHub workflow input and the same approval
gate.

## Implementation Changes

### Release checks

Add release checks before image publishing:

- Identity: Ruff, mypy, pytest with coverage, and package build.
- Central API: Ruff, mypy, pytest with its 90% coverage gate, and package build.
- Shared Python packages used by production images: tests, static checks, and builds.
- Back Office and shared TypeScript: install, type-check, lint, unit tests, and production build.
- Any failure prevents image publishing and deployment approval.

### Production deployment workflow

Add a reusable `.github/workflows/deploy-production.yml` that:

- Accepts only `sha-` followed by a 40-character lowercase commit SHA.
- Supports calls from the image workflow and manual dispatch for rollback.
- Confirms Identity, Central API, and Back Office manifests exist in GHCR.
- Uses a `production` GitHub Environment requiring approval.
- Serializes deployments so two releases cannot modify Coolify concurrently.
- Reads the existing Coolify environment configuration.
- Selects exactly one production (non-preview) `TRACKFLOW_IMAGE_TAG`, requires
  Buildtime and Runtime, and preserves its metadata plus every other production
  and preview environment record.
- Triggers the Coolify deployment webhook.
- Parses Coolify 4.1.2's deployment response envelope and polls the returned
  deployment until success, failure, or timeout.
- Writes the deployed SHA and result to the GitHub job summary.
- Never runs migrations or seeds.

### Container image workflow

Update `.github/workflows/container-images.yml` to:

- Make image publication depend on successful release checks.
- Call the deployment workflow after all three images publish from `main`.
- Never deploy pull-request builds.
- Prevent cancellation once a production deployment has started.

### One-time external configuration

- Enable Coolify API access and create a least-privilege deployment/environment-update token.
- Create GitHub's `production` Environment with approval required.
- Add environment secrets `COOLIFY_TOKEN`, `COOLIFY_WEBHOOK`,
  `COOLIFY_BASE_URL`, and `COOLIFY_APPLICATION_UUID`.
- Keep Coolify's native Git auto-deploy disabled to avoid racing image publication.

Coolify supports API-token/webhook deployment from GitHub Actions and environment updates through
its application API:

- [GitHub Actions guide](https://coolify.io/docs/applications/ci-cd/github/actions/)
- [Environment API](https://coolify.io/docs/api-reference/api/applications/update-envs-by-application-uuid)

### Documentation

Update the deployment runbook and workflow README with normal release, approval, rollback, timeout,
and secret-rotation instructions.

## Failure and Rollback Behavior

- Missing images, failed checks, invalid tags, API failures, or webhook failures stop the workflow
  before subsequent mutations.
- Deployment failure does not automatically roll back; GitHub clearly reports the failed SHA.
- For rollback, manually run `deploy-production.yml`, enter a known-good immutable SHA tag, approve
  Production, and let the workflow redeploy it.
- Other Coolify secrets and environment variables remain untouched.

## Verification

- Validate workflow syntax with `actionlint` and run `git diff --check`.
- Confirm pull-request runs never deploy and failed release checks never publish.
- Test invalid and nonexistent rollback tags.
- Perform the first approved deployment and verify:
  - Coolify references the expected SHA.
  - Identity, Central API, and Back Office are healthy.
  - Migration and seed profile services remain stopped.
  - Only Back Office is publicly routed.
  - HTTPS, login, authenticated pages, inventory, suppliers, and incidents remain correct.
- Confirm no tokens, webhook URLs, credentials, admin identifiers, or environment values enter git
  history.

## Assumptions

- Production deployments require a GitHub approval click.
- Rollbacks use the same approval gate.
- GHCR images remain public.
- Documentation-only commits outside the existing image path filters do not deploy.
- Full browser E2E and security-scanning workflows remain separate follow-up work; this change
  automates the production release checks needed by the three deployed images.
