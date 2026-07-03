# Deployment and Dockerization Brief

## Status

Repository implementation complete; external infrastructure and production
execution remain approval-gated. Production images are built on GitHub-hosted
Actions runners and pulled from GHCR so the small VPS stays runtime-focused.

## Acceptance criteria

- Public website remains Vercel-native and is not containerized.
- Coolify deploys one Compose stack containing Back Office, Identity, and
  Central API; only Back Office is publicly routed.
- Identity remains single-worker TinyDB with a persistent volume and receives
  the RS256 private key. Central API receives only the public key.
- Runtime and migration database identities remain separate. Migrations and
  seeds are explicit setup-profile one-offs and never run at app startup.
- Production incidents start empty.
- Local and production Compose files stay separate.
- Backup/restore, rollback, health checks, secrets, and deployment order are
  documented. For this portfolio deployment, the owner explicitly accepts
  disposable Supabase and Identity data without scheduled backups.

## Deferred owner inputs

Confirmed owner decisions:

- Supabase Free in `us-east-2`, reached through Supavisor Session mode on IPv4
  port 5432 with TLS.
- Supabase and Identity data are disposable portfolio data; recovery is
  redeploy, recreate users, migrate, and reseed. This is not production-grade
  durability.
- Build the three production images in GitHub Actions and publish them to GHCR.
- Use `coolify.forgehub.cloud` for the Coolify dashboard.

Still required: verified Resend sender and a decision on whether the existing
Supplier TinyDB data is authoritative. No external operation may infer these
values.
