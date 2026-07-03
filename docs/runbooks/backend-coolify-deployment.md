# Backend and Back Office Coolify Deployment

## Status

Prepared, not production-verified. Every production migration, seed, DNS,
firewall, and deployment action requires explicit owner approval.

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

## Rollback

Set `TRACKFLOW_IMAGE_TAG` to the previous published `sha-<full-commit>` tag and
redeploy the Compose stack. Never automatically downgrade the schema; use
expand/contract and forward fixes. With the accepted no-backup waiver, a
database or Identity-volume loss is recovered by recreation rather than restore.
