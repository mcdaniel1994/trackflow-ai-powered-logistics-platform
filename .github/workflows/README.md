# CI Workflows

**Status:** Release checks, container publishing, and approval-gated production deployment are
implemented. Broad pull-request CI, browser E2E, and security scanning remain planned. **Do not
create empty or non-functional workflow YAML** — add a `.yml` file only when it contains valid,
purposeful behavior.

This CI design enforces the quality gates defined in
[`docs/standards/production-readiness.md`](../../docs/standards/production-readiness.md). That
standard is the source of truth for *what* must pass; the workflows here are *how* it gets enforced.

---

## Implemented workflows

| File | Trigger | Purpose |
|---|---|---|
| `release-checks.yml` | Reusable `workflow_call` | Runs production-target Ruff/mypy/pytest/coverage/build checks and npm type-check/lint/test/build checks with a non-fail-fast matrix. |
| `container-images.yml` | Relevant PR, push to `main`, and manual dispatch | Calls release checks first, builds Linux AMD64 images on PRs, and publishes `main` plus immutable `sha-<commit>` tags only for non-PR runs. |
| `deploy-production.yml` | Reusable `workflow_call` and manual dispatch | Waits for Production approval, migrates/verifies the target image, deploys its immutable SHA, polls readiness and smoke tests, and restores the prior image on failure. Manual `image-rollback` never downgrades the database. |

`container-images.yml` calls `deploy-production.yml` only after all three images publish from
`main`. Pull requests run release checks and image builds but never publish or deploy. Production
deployments are serialized and are not cancelled after they start.

The release workflow now machine-enforces:

- Identity, Central API, and Data Pipelines Ruff, mypy, pytest coverage, and package builds. Data
  Pipelines also executes its cache-disabled direct CLI before the test suite. Central API and Data
  Pipelines retain configured 90% coverage floors and test after applying the schema to ephemeral
  local PostgreSQL. Identity reports coverage without a hard floor.
- `trackflow_auth` and `trackflow_incidents` tests, static checks, and package builds.
- Back Office type-check, lint, unit tests, and production build.
- Shared TypeScript type-check and build. `packages/shared` has no standalone lint or test scripts;
  its runtime behavior remains exercised by its consuming Back Office suite.
- Production migration role/lock/grant/idempotency tests and mocked Coolify mutation, failure,
  timeout, and image-rollback tests.

These checks gate production image publication. They are not yet a broad path-aware `ci.yml`
required check for every repository change.

## Planned workflow files

Add these only when implemented with real behavior:

| File | Trigger | Purpose |
|---|---|---|
| `ci.yml` | PR + push to `main` | Broad per-package checks outside the production-image path filters and required-check integration for branch protection. |
| `e2e.yml` | PR (paths: `uis/backoffice/**`) | Run the Playwright e2e suite (`uis/backoffice/tests/e2e/`). |
| `security.yml` | PR + schedule | Dependency vulnerability scan and secret scanning; aligns with the security gate in `production-readiness.md`. |

## How PRs, merges, and deployments interact

- **Pull request →** relevant changes call `release-checks.yml` and build all three images without
  publishing them. Future `ci.yml`, `e2e.yml`, and `security.yml` workflows should become required
  status checks when implemented.
- **Merge to `main` →** relevant changes pass release checks, publish all three immutable images,
  then wait at the GitHub `production` Environment approval gate.
- **Production approval →** `deploy-production.yml` confirms manifests, runs the image's fail-closed
  migration/grant verifier, updates only the Coolify image tag, deploys, polls readiness, and checks
  unauthenticated protection. Deployment/readiness failure restores the prior image tag; it never
  downgrades the database.
- **Rollback →** manually dispatch with a known-good immutable tag, choose `image-rollback`, and
  approve the same Production environment. This skips migrations and relies on expand/contract
  compatibility.
- **Vercel →** the public website remains independently deployed through Vercel; its preview and
  production builds are separate from these backend/Back Office workflows.

See
[`docs/runbooks/backend-coolify-deployment.md`](../../docs/runbooks/backend-coolify-deployment.md)
for owner setup, normal deployment, rollback, timeout, and credential-rotation procedures.

## Implementation checklist

- [x] Publish deployable images through GitHub Actions and GHCR.
- [x] Add reusable production-target release checks.
- [x] Wire Central API's configured coverage floor and Identity coverage reporting.
- [x] Add approval-gated, SHA-pinned Coolify deployment and manual rollback dispatch.
- [ ] Add broad `ci.yml` coverage for repository changes outside image path filters.
- [ ] Add `e2e.yml` for Back Office Playwright.
- [ ] Add `security.yml` dependency + secret scanning.
- [ ] Enable/update branch protection to require the intended checks.
- [ ] Reconcile GitHub checks with Vercel preview/production builds.
