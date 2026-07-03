# CI Workflows — Intended Architecture (scaffolding)

**Status:** Container publishing is automated by `container-images.yml`.
Application quality/security CI remains planned. **Do not create empty or
non-functional workflow YAML** — add a `.yml` file only when it contains valid,
purposeful behavior.

This CI design enforces the quality gates defined in
[`docs/standards/production-readiness.md`](../../docs/standards/production-readiness.md). That
standard is the source of truth for *what* must pass; the workflows here are *how* it gets enforced.

---

## Current State (verified)

- `container-images.yml` builds the three production images on GitHub-hosted
  runners and publishes `main` plus immutable `sha-<commit>` tags to GHCR.
- No automated application test, coverage, or security workflow exists yet.
- No pre-commit hooks; no coverage gating is wired.
- Tests run locally per [`docs/standards/testing.md`](../../docs/standards/testing.md).
- The public website is deployed via Vercel (see
  [`docs/runbooks/frontend-vercel-deployment.md`](../../docs/runbooks/frontend-vercel-deployment.md)).
  Vercel builds/deploys are managed in the Vercel platform, separate from these GitHub workflows.

## Planned Workflow Files

Add these only when implemented with real behavior:

| File | Trigger | Purpose |
|---|---|---|
| `container-images.yml` | Relevant PR, push to `main`, and manual dispatch | Build Linux AMD64 images on PRs; publish `main` and immutable commit tags to GHCR after merge or manual dispatch. |
| `ci.yml` | PR + push to `main` | Per-package lint, `type-check`, build, and unit/integration tests (Python services via `uv`, UIs/packages via npm workspaces). Enforce the coverage policy from `testing.md`. |
| `e2e.yml` | PR (paths: `uis/backoffice/**`) | Run the Playwright e2e suite (`uis/backoffice/tests/e2e/`). |
| `security.yml` | PR + schedule | Dependency vulnerability scan and secret scanning; aligns with the security gate in `production-readiness.md`. |
| `deploy.yml` | optional | Future automatic Coolify trigger after images publish. `container-images.yml` deliberately does not deploy. |

## Required Quality Gates (must pass before merge)

These mirror [`docs/standards/production-readiness.md`](../../docs/standards/production-readiness.md):

1. Lint + `type-check` clean for every touched package/app.
2. Build succeeds for every touched package/app.
3. Unit/integration tests pass; coverage is preserved or improved (no silent regression).
4. e2e suite passes for back-office changes.
5. Dependency/secret scan shows no new high-severity findings.

## How PRs, Merges, and Vercel Deploys Should Interact

- **Pull request →** `ci.yml` (and `e2e.yml`/`security.yml` where paths match) run as required
  status checks. A PR cannot merge with a failing required check.
- **Vercel preview →** Vercel builds a preview deployment per PR independently of GitHub Actions.
  Treat the preview as a review aid; the required gates above are still the CI checks, not the
  preview build.
- **Merge to `main` →** `ci.yml` runs on `main`; Vercel promotes the production deployment for the
  public website from `main`. Keep branch protection requiring the CI checks so `main` stays green.
- **Backend services** deploy through Coolify from prebuilt GHCR images named
  in `compose.coolify.yaml`. Production migrations and seeds remain explicit
  one-offs, not Actions jobs.

## Implementation Checklist (follow-up, out of scope for this docs task)

- [x] Publish deployable images through GitHub Actions and GHCR.
- [ ] Decide quality-CI provider config (matrix for `uv` Python projects + npm workspaces).
- [ ] Add `ci.yml`: lint, type-check, build, test for changed packages.
- [ ] Wire coverage reporting and the threshold/ratchet from `testing.md`.
- [ ] Add `e2e.yml` for back-office Playwright.
- [ ] Add `security.yml` dependency + secret scanning.
- [ ] Enable branch protection on `main` requiring the checks above.
- [ ] Reconcile GitHub checks with Vercel preview/production builds.
- [ ] Update `production-readiness.md` to mark which gates became automated.
