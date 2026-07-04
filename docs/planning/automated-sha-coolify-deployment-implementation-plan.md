# Codex Implementation Plan — Automated SHA Deployment to Coolify

> Companion to [automated-sha-coolify-deployment.md](automated-sha-coolify-deployment.md) (the spec).
> This is the repository-side execution plan.

## Context

TrackFlow publishes three production images (Identity, Central API, Back Office) to GHCR via
[.github/workflows/container-images.yml](../../.github/workflows/container-images.yml). Today
publishing happens on every eligible `main` push with **no quality gate**, and production deployment
to Coolify is a fully manual runbook procedure
([docs/runbooks/backend-coolify-deployment.md](../runbooks/backend-coolify-deployment.md)): an
operator sets `TRACKFLOW_IMAGE_TAG` to an immutable `sha-<40hex>` tag and redeploys the Compose stack
by hand.

The spec in [automated-sha-coolify-deployment.md](automated-sha-coolify-deployment.md) defines the
target: gate publishing on release checks, then run an **approval-gated, SHA-pinned** deployment that
updates only `TRACKFLOW_IMAGE_TAG` in Coolify and verifies the exact SHA. Rollback is the same
workflow run manually with a known-good SHA. The intent is safe, reproducible, immutable-tag
production releases with a human approval click — **never** running migrations/seeds and **never**
touching other Coolify settings.

This plan implements the complete **repository side** only. All GitHub Environment/secret creation
and Coolify token/webhook setup are reported as manual steps for the owner (Cory) — codex must not
touch external systems, must not push, and must not open a PR without explicit approval.

**Decisions locked with the owner:**
- Release checks live in a **dedicated reusable `release-checks.yml`** (keeps the reserved `ci.yml`
  name free for the later broad PR-CI effort).
- Identity gets **`ruff`, `mypy`, `pytest-cov` added to its dev extras** so checks run uniformly
  across both Python services (integration-only metadata change, permitted by AGENTS.md Protected
  Paths as active-engagement cleanup).

## Branch & Guardrails

- Work on a **`codex/` feature branch** (e.g. `codex/automated-sha-coolify-deploy`) — `main` is
  protected. Do **not** push or open a PR without asking Cory first.
- **Preserve unrelated worktree changes.** Only stage files this plan touches.
- **No secrets in any workflow output or committed file.** Secrets are consumed only from GitHub
  Environment secrets at runtime and never `echo`ed, written to `$GITHUB_OUTPUT`, or put in job
  summaries. Mask any dynamic value derived from a secret with `::add-mask::`.
- **Never run migrations or seeds** — the deploy workflow updates only `TRACKFLOW_IMAGE_TAG` and
  triggers the app deploy; the `setup`-profile services in
  [compose.coolify.yaml](../../compose.coolify.yaml) stay stopped.
- **Do not redeploy production** during implementation. Verification is syntax/lint/dry-run only.
- Follow `.agents/rules/testing-error-handling-ci.md` → `docs/standards/production-readiness.md`,
  `testing.md`, `error-handling.md`, `observability.md`.

## Files to Change

### 1. New: `.github/workflows/release-checks.yml` (reusable, `workflow_call`)
Gate that must pass before any image publishes. One job per production build target, `fail-fast:
false` so all report:
- **Identity** (`services/identity`): `ruff check`, `mypy`, `pytest --cov` (report coverage; do not
  add a hard threshold Identity can't yet meet — see Risks), and `python -m build` / `uv build`.
- **Central API** (`services/central-api`): `ruff check`, `mypy`, `pytest --cov` honoring its
  existing `fail_under = 90` from `pyproject.toml`, and package build.
- **Shared Python used by images** (`packages/trackflow_auth`, `packages/trackflow_incidents`):
  their tests + static checks + build (both are baked into the images).
- **Back Office + shared TS** (`uis/backoffice`, `packages/shared`): `npm ci` at root, then
  `npm run type-check`, `lint`, `test`, `build` for the touched workspaces.
- Pin action versions (`actions/checkout@v4`, `actions/setup-node@v4`, `astral-sh/setup-uv@v6`).
- `permissions: contents: read` only.

### 2. New: `.github/workflows/deploy-production.yml` (reusable + `workflow_dispatch`)
- **Inputs:** `image_tag` (string). Validate with strict regex `^sha-[0-9a-f]{40}$` in the first
  step; fail fast otherwise. `workflow_call` from `container-images.yml` passes the just-built SHA
  tag; `workflow_dispatch` accepts a manual tag for **rollback**.
- **Environment:** `environment: production` (approval enforced by the GitHub Environment Cory
  creates) — this is the human approval gate.
- **Concurrency:** `group: deploy-production`, `cancel-in-progress: false` so two releases cannot
  mutate Coolify concurrently and an in-flight deploy is never cancelled.
- **Manifest preflight:** confirm all three GHCR images expose that tag before mutating anything
  (`docker buildx imagetools inspect ghcr.io/mcdaniel1994/trackflow-<svc>:<tag>` for identity,
  central-api, backoffice). Any miss → fail before touching Coolify.
- **Coolify env update:** read current app env, select exactly one production
  (`is_preview == false`) `TRACKFLOW_IMAGE_TAG`, and update only that record.
  Require Buildtime+Runtime, preserve its accepted metadata explicitly, and
  verify every other production/preview record by UUID remains unchanged.
  Base URL/UUID come from Environment **variables**; the token comes from an
  Environment **secret**. Curl uses `--fail-with-body` and Bearer authorization;
  never print the token or full response bodies that could echo secrets.
- **Trigger + poll:** call the Coolify deploy webhook, capture the returned
  deployment id (including Coolify 4.1.2's
  `deployments[0].deployment_uuid` envelope), and poll its status until
  `finished`/`failed`/timeout (bounded loop, ~15 min). Timeout/failure → job
  fails with a clear message; **no auto-rollback**.
- **Summary:** write deployed SHA + result to `$GITHUB_STEP_SUMMARY` (SHA and status only — no
  secrets, URLs, or env dumps).
- **Never** enable the `setup` profile / migrations / seeds.

### 3. Update: `.github/workflows/container-images.yml`
- Add a `checks` job that `uses: ./.github/workflows/release-checks.yml`; make the `publish` matrix
  `needs: checks` so a failed gate blocks publishing.
- After all three images publish **from `main` only** (`if: github.ref == 'refs/heads/main' &&
  github.event_name != 'pull_request'`), call `deploy-production.yml` with the built `sha-<sha>` tag.
  PR builds must never deploy (existing `push: ${{ github.event_name != 'pull_request' }}`
  preserved).
- Ensure a started production deploy is not cancelled: keep `cancel-in-progress: true` for the
  build/publish group, but the deploy job/group uses its own non-cancelable concurrency (handled in
  `deploy-production.yml`).

### 4. Update: `services/identity/pyproject.toml`
Add `ruff`, `mypy`, `pytest-cov` to the `dev` optional-dependencies (integration-only metadata). Add
minimal `[tool.ruff]`/`[tool.mypy]` config only if needed to keep the gate green without a large
pre-existing-findings cleanup; if either surfaces broad pre-existing issues, scope the check narrowly
and note it (see Risks) rather than doing an unrelated refactor.

### 5. Update docs
- **`.github/workflows/README.md`**: move `container-images.yml` + `release-checks.yml` +
  `deploy-production.yml` to implemented state; record which release gates are now machine-enforced;
  keep `ci.yml`/`e2e.yml`/`security.yml` as remaining planned work; reconcile the `deploy.yml` row
  (now realized as `deploy-production.yml`, approval-gated, SHA-pinned).
- **`docs/runbooks/backend-coolify-deployment.md`**: add an "Automated SHA deployment" section
  (normal flow: merge → checks → publish → approve `production` → verify) and rewrite **Rollback** to
  run `deploy-production.yml` via `workflow_dispatch` with a known-good `sha-<40hex>` tag + approval.
  Document timeout behavior and **secret rotation** (`COOLIFY_TOKEN`, `COOLIFY_WEBHOOK`).
- **`docs/runbooks/README.md`**: flip the relevant Implementation Checklist items and note the
  automated-deploy runbook section.
- Keep [automated-sha-coolify-deployment.md](automated-sha-coolify-deployment.md) as the spec of
  record and commit it alongside this plan.

### 6. Engagement-tracking docs (AGENTS.md pre-commit workflow)
Update `memory-bank/progress.md` ("Open Decisions And Known Risks" → CI release-gating +
approval-gated Coolify deploy now implemented) and `memory-bank/techContext.md` (workflow inventory).
Touch only what this change makes true; do not overstate (no live rollback drill has run).

## Reuse / Existing Patterns
- Exact test/build commands come from `docs/standards/testing.md §4` and each `pyproject.toml` /
  `package.json` — reuse verbatim (`uv run --project <svc> --extra dev pytest`, npm workspace
  scripts). Do not invent runners.
- Central API's coverage gate (`fail_under = 90`) lives in config; the workflow just runs pytest.
- Image names + Dockerfiles are already in the `container-images.yml` matrix — reuse for the manifest
  preflight.
- Tag format `sha-<full-commit>` is produced by `docker/metadata-action` and consumed by
  `compose.coolify.yaml` `TRACKFLOW_IMAGE_TAG` — match it exactly.

## Verification (repo-side only — do NOT deploy)
1. `actionlint` on all three workflow files; fix all findings.
2. `git diff --check`.
3. Run the affected quality gates locally to prove the release-checks commands:
   - Central API: `ruff check`, `mypy`, `pytest --cov`.
   - Identity (after dev-dep addition): `ruff check`, `mypy`, `pytest --cov`.
   - `packages/trackflow_auth`, `packages/trackflow_incidents`: tests + checks + build.
   - `npm ci` then type-check/lint/test/build for `uis/backoffice` and `packages/shared`.
   - Package builds for both services.
4. Confirm the SHA regex rejects invalid/nonexistent tags (test locally; do not reach Coolify steps).
5. Secret-scan the final diff: `git diff | rg -i 'token|secret|webhook|bearer|password|uuid|forgehub'`
   plus a manual read.
6. Reason through `container-images.yml` so a `pull_request` event runs checks but never
   publishes/deploys.

## Report Back (stop when repo changes are ready)
1. Files changed.
2. Tests/checks run and results (actionlint, `git diff --check`, each gate, secret scan).
3. Remaining external setup (below).
4. Recommended additional workflows this round: `e2e.yml` (Playwright, PR path-filtered) and
   `security.yml` (dependency + secret scanning) — both reserved in the workflow README.
5. Exact GitHub + Coolify manual config (below).
6. Risks / API-compat questions (below).

## Manual External Setup (owner-only — codex must NOT do these)
- **GitHub:** create a `production` Environment with **required reviewers**. Add Environment
  **secrets** `COOLIFY_TOKEN`, `COOLIFY_WEBHOOK`; Environment **variables** `COOLIFY_BASE_URL`,
  `COOLIFY_APPLICATION_UUID`. Confirm branch protection still passes with new required checks.
- **Coolify:** create a least-privilege API token (deploy + env-update only), capture the deploy
  webhook URL and application UUID, and **keep native Git auto-deploy disabled** so it can't race
  image publication.

## Risks / Open Questions
- **Coolify 4.1.2 compatibility (repository behavior verified):** its env GET
  merges production and preview records; its per-key PATCH selects production
  when `is_preview` is false and preserves Buildtime/Runtime when explicitly
  supplied; its deploy response nests the id under
  `deployments[0].deployment_uuid`. The workflow handles those contracts, but
  API Access, the production Buildtime flag, native Git auto-deploy, and the
  first live deployment remain owner-controlled external steps.
- **Identity static-analysis baseline:** Identity has never run `ruff`/`mypy`; enabling them may
  surface pre-existing findings. Keep the gate green with minimal config or narrowly scoped rules and
  flag cleanup as follow-up — do not silently lower quality or do a large unrelated refactor. No hard
  coverage `fail_under` on Identity yet.
- **Deploy polling contract:** the parser covers Coolify 4.1.2's response and
  status field plus the previously documented compatible envelopes; unknown
  statuses fail closed and the bounded loop times out safely (no hang or
  auto-rollback).
- **No live production validation here:** the full approved-deploy verification in the spec can only
  be done by Cory on the first real approved run — a post-merge owner step.
