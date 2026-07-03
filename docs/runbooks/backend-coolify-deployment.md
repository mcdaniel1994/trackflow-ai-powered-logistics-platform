# Backend and Back Office Coolify Deployment

## Status

Production-verified on July 3, 2026 UTC (July 2 America/Chicago). Future
production migrations, seeds, DNS, firewall, deployment, and rollback actions
still require explicit owner approval.

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
  Buildtime and Runtime, even though this stack pulls prebuilt images. Keep both
  JWT values marked Multiline.
- Keep Coolify automatic deployment disabled initially. A push to `main` can
  reach Coolify before GitHub Actions finishes publishing all three images;
  deploy manually only after the workflow is green.

## Order

1. Confirm GitHub Actions published all three `sha-<full-commit>` images for
   the same commit, then set `TRACKFLOW_IMAGE_TAG` to that immutable tag.
2. Create least-privilege database roles using the Supabase runbook.
3. Test the migration on a disposable target.
4. Run `central-api-migrate` as an explicit setup-profile one-off.
5. Deploy Identity with its persistent volume; verify `/health`.
6. Run `python -m identity.cli create-admin` in the Identity container and
   securely record its stable UUID.
7. Run `seed-inventory` with that UUID, then `seed-suppliers`. Never run
   `seed-incidents` in production.
8. Deploy Central API and verify `/health` reports database `ok`.
9. Deploy Back Office and route only port 3000 through Traefik.
10. Verify HTTPS login, `Secure; HttpOnly` cookies, CSRF writes, reset email,
   inventory, incidents, suppliers, and all health endpoints.
11. Confirm internet requests cannot reach Identity or Central API.

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

Set `TRACKFLOW_IMAGE_TAG` to the previous published `sha-<full-commit>` tag and
redeploy the Compose stack. Never automatically downgrade the schema; use
expand/contract and forward fixes. With the accepted no-backup waiver, a
database or Identity-volume loss is recovered by recreation rather than restore.
