# Backend and Back Office Coolify Deployment

## Status

Base production deployment verified on July 3, 2026 UTC (July 2 America/Chicago). The first
dedicated-Prefect production release on July 15 failed during Compose startup; the repository
hotfix is implemented and awaiting an approved redeployment. Future production mutations still
require the GitHub Production reviewer approval. The hardened release workflow now
migrates, verifies grants, deploys declarative workers, polls dependency-aware readiness,
smoke-tests unauthenticated protection, and restores the previous image tag on failure.

## July 15, 2026 Prefect startup incident

The first dedicated-Prefect release reached Supabase migration `20260716_0010`, but the application
stack did not become ready. Coolify materialized both relative file bind mounts intended for
`/docker-entrypoint-initdb.d` as **directories**. PostgreSQL therefore started and accepted
connections without creating `pg_trgm` or the `prefect_backup` role. Because the named data volume
was already initialized, retries correctly logged `Skipping initialization` and could never repair
those missing prerequisites. The extension-aware database health check stayed unhealthy, so the
Prefect server, guards, and reporting worker remained blocked in `Created` state.

The permanent safeguards are:

- PostgreSQL bootstrap files are copied into a digest-pinned custom image; production startup no
  longer relies on Coolify translating repository file bind mounts correctly.
- A one-shot `prefect-postgres-bootstrap` service reapplies the idempotent extension and backup-role
  setup on **every deployment**, including an already-initialized volume, before Prefect starts.
- PostgreSQL container health proves only that PostgreSQL accepts connections. The bootstrap and
  existing release guard separately prove the extension, role, and Prefect schema prerequisites.
- The Central API image health check uses `/health/live`. The deployment workflow still checks
  `/health/ready` after the complete dependency graph has started.
- Regression tests reject init-script bind mounts, a missing bootstrap dependency, and use of
  dependency-aware readiness as the container liveness probe.

Do **not** delete or recreate `prefect-db` to recover this incident. The bootstrap is designed to
repair that volume in place without touching Supabase or TrackFlow business data.

## Verified production record

- Public entrypoint: `https://backoffice.forgehub.cloud`; Identity and Central
  API have no Coolify domains or host-port mappings.
- Coolify imported source commit `be05a15`. The initial containers used immutable
  image tag `sha-06f3fdec53e345fae337a323215aa4b3cab13720`; the intervening
  commit changed only `docs/runbooks/README.md` and
  `docs/runbooks/supabase-migrations.md`, not runtime code.
- Identity, Central API, and Back Office health checks passed. Migration and
  seed profile services did not start during the normal deployment.
- Supabase reached Alembic revision `20260702_0003`; the runtime role's CRUD
  access was verified across all six tables.
- The first Identity admin was created and its UUID stored only in Coolify as
  `SEED_USER_UUID`. Inventory and 15 suppliers were seeded after separate
  approval; incidents remained empty.
- HTTPS, a trusted certificate, `Secure`/`HttpOnly`/`SameSite=Lax` cookie
  flags, CSRF-protected profile writes, logout, password reset, authenticated
  inventory/supplier/incident pages, and private backend exposure were verified.
- Supabase Free and the Identity volume still have no scheduled backups under
  the accepted disposable-data waiver.
- Coolify `4.1.2` API access is enabled; the production image-tag variable is
  available at Buildtime and Runtime; native Git auto-deploy is disabled; and
  the GitHub Production environment has required review, a `main`-only rule,
  and four masked deployment secrets. Add rotated `MIGRATION_DATABASE_URL` as the fifth
  approval-protected secret before enabling the hardened flow. No token, webhook URL, UUID, environment
  value, or production coordinate is recorded here.

## Prerequisites

- Confirm the remaining owner inputs in `docs/planning/deployment-dockerization.md`.
- Acknowledge the portfolio-only durability waiver: Supabase Free and Identity
  have no scheduled backups, so loss requires redeploying and recreating data.
- Store secrets only in Coolify. Identity receives the private and public JWT
  keys; Central API receives only the public key.
- Use the exact Supabase direct or Session-mode connection strings from its
  dashboard with `sslmode=require`; never use transaction mode `:6543`.
- Confirm the `trackflow-identity`, `trackflow-central-api`, and
  `trackflow-backoffice` GHCR packages are public, or authenticate the VPS to
  GHCR with a least-privilege `read:packages` token.
- Set `TRACKFLOW_IMAGE_TAG` to the published immutable
  `sha-<full-commit>` tag. The workflow also publishes `main` for inspection,
  but deployments are pinned to a commit.
- Coolify runs Docker Compose interpolation with `build-time.env`. Every
  production variable referenced with `${NAME:?required}` must be available at
  Buildtime and Runtime. App services pull prebuilt images while supporting infrastructure images
  may build from repository Dockerfiles. Keep both
  JWT values marked Multiline.
- Keep Coolify native Git auto-deploy disabled. GitHub Actions publishes and
  preflights all three images before an approved deployment, and a native
  Coolify push hook would race that sequence.

## Automated SHA deployment

Normal production releases use `.github/workflows/container-images.yml` and
`.github/workflows/deploy-production.yml`:

1. Merge an eligible runtime or workflow change to `main`.
2. Wait for every job in `release-checks.yml` to pass.
3. Confirm all three GHCR image jobs publish the same immutable
   `sha-<40-lowercase-hex>` tag.
4. Review and approve the waiting GitHub `production` Environment deployment.
5. The workflow runs the target image's `central-api-migrate`, records before/after revisions,
   verifies runtime grants, statically checks the pinned Prefect client/server contract, then
   mutates only the non-preview `TRACKFLOW_IMAGE_TAG`.
6. It polls Coolify, then Back Office's Identity/Central readiness aggregate and expected
   unauthenticated reporting protection. The reporting worker cannot start until the live Prefect
   PostgreSQL-fallback and digest-mapped version guards pass. Deployment/readiness failure restores
   the prior app image without changing Prefect Server or downgrading either database.
7. Review the GitHub summary for SHA, revisions, Prefect guards, readiness, smoke tests, and rollback state.

Before enabling the first run, create the GitHub `production` Environment with
required reviewers. Store `COOLIFY_TOKEN`, `COOLIFY_WEBHOOK`,
`COOLIFY_BASE_URL`, `COOLIFY_APPLICATION_UUID`, and the rotated
`MIGRATION_DATABASE_URL` as Environment secrets so
GitHub masks every production coordinate before the runner starts. The Coolify
token needs only the permissions required to list application environment
metadata, update one environment variable, and inspect and trigger deployments:
current Coolify v4 names those token permissions `read`, `write`, and `deploy`.
Do not grant `root`; `read:sensitive` is not needed by this workflow.

Coolify `4.1.2` returns production and preview environment records together
from the application env endpoint, even when preview deployments are disabled.
The workflow distinguishes them with `is_preview` and updates only the
production record. It also accepts the `deployments[0].deployment_uuid`
response envelope returned by that version's authenticated deploy webhook.

Rotate either credential by replacing its GitHub Environment secret:

- For `COOLIFY_TOKEN`, create and test a replacement least-privilege token,
  replace the secret, then revoke the old token.
- For `COOLIFY_WEBHOOK`, rotate the deploy webhook in Coolify, replace the
  secret, and invalidate the previous webhook.

Never print either value, paste it into an issue or workflow input, or commit it.
After rotation, use an approved deployment of a known immutable SHA to verify
the integration; do not use migrations or seeds as a credential test.

## Runtime topology

Normal deployment starts `identity`, `central-api`, `backoffice`, `operations-feed`,
`reporting-worker`, `maintenance-worker`, private `prefect-server`/`prefect-postgres`, and the
isolated `prefect-db-backup` service. The one-shot PostgreSQL bootstrap must complete before Prefect
Server or its backup service starts; the two one-shot Prefect guards must then complete before the
reporting worker starts. Do not configure separate dispatcher, runner, prune, backup, or size-guard
cron jobs. Worker services use one replica, read-only filesystems, `/tmp` tmpfs mounts, limits, and
restart-on-failure.

## Order

1. Confirm GitHub Actions published all three `sha-<full-commit>` images for
   the same commit, then set `TRACKFLOW_IMAGE_TAG` to that immutable tag.
2. Create least-privilege database roles using the Supabase runbook.
3. Test the migration on a disposable target; the approved workflow then runs and verifies it.
4. Approve the GitHub Production deployment; let it migrate, deploy, and verify all services.
5. For initial setup only, run `python -m identity.cli create-admin` in the Identity container and
   securely record its stable UUID.
6. For initial setup only, run `seed-inventory` with that UUID, then `seed-suppliers`. Never run
   `seed-incidents` in production.
7. Verify `/health/live`, `/health/ready`, `/health`, and the Back Office aggregate.
8. Verify HTTPS login, `Secure; HttpOnly` cookies, CSRF writes, reset email,
   inventory, incidents, suppliers, and all health endpoints.
9. Confirm internet requests cannot reach Identity or Central API.

In Coolify, run setup services explicitly from `compose.coolify.yaml`; a normal
stack deploy must not enable the `setup` profile.

For the initial verified rollout, the separately approved seeds were executed
one at a time from the running Central API container:

```bash
cd /app/services/central-api
SEED_USER_UUID=<existing-identity-user-uuid> .venv/bin/seed-inventory
.venv/bin/seed-suppliers
```

Stop after any failure and inspect non-secret logs before retrying. Never run
`seed-incidents` in production.

## Troubleshooting

- `prefect-postgres` is running and `pg_isready` succeeds, but `pg_trgm` or `prefect_backup` is
  absent: inspect `prefect-postgres-bootstrap`. It must complete with the fixed token
  `prefect_postgres_bootstrap=complete`. Do not wait for PostgreSQL's init directory to rerun and do
  not delete the named volume.
- A path under `/docker-entrypoint-initdb.d` appears as `drwx...` in a deployed container: stop and
  treat it as a Compose/platform mount-translation defect. Required init files must be image-baked,
  never production relative bind mounts.
- `required variable TRACKFLOW_IMAGE_TAG is missing a value` before containers
  start means the variable is unavailable in Coolify's build phase. Enable both
  Buildtime and Runtime availability for every required Compose variable.
- `JWSError` or `MalformedFraming` during login means a JWT PEM is incomplete
  or malformed. Paste the complete matching key pair, including the exact
  `-----BEGIN ...-----` and `-----END ...-----` lines, without variable names
  or surrounding quotes. Identity now validates the pair during startup.
- Chrome can retain a temporary permission to run active content with
  certificate errors even after Coolify has a valid certificate. If Incognito
  is secure but the normal profile reports broken HTTPS, reset the site's
  permissions/data and fully quit and reopen Chrome before changing server
  configuration.

## Rollback

1. In GitHub Actions, select **Deploy production** and choose **Run workflow**.
2. Enter the known-good `sha-<40-lowercase-hex>` image tag and choose `image-rollback`.
3. Approve the waiting `production` Environment deployment.
4. Wait for manifest preflight and Coolify polling to finish, then perform the
   health and authenticated-path checks from the automated flow above.

Invalid tags and tags missing any manifest fail before mutation. Manual image rollback uses the
same approval gate, skips migrations, and never downgrades the database. Every migration must
preserve the previous image through expand/backfill/deploy/contract compatibility.

An image rollback changes `TRACKFLOW_IMAGE_TAG`; it does **not** restore an earlier
`compose.coolify.yaml`. If a release changes Compose topology and that topology is the failure,
restoring the prior app image can fail in the same way. Recover by deploying a reviewed forward
hotfix or by explicitly redeploying the prior repository revision through an owner-approved
procedure. Never interpret a successful tag mutation as proof that Compose-level rollback occurred.

No live automated rollback drill has run yet. With the accepted no-backup
waiver, a database or Identity-volume loss is recovered by recreation rather
than restore.
