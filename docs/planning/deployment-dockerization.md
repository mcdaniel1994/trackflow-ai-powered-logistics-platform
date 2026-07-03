# Deployment and Dockerization Brief

## Status

Repository implementation complete; external infrastructure and production
execution remain approval-gated.

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
  documented before any production account is created.

## Deferred owner inputs

Confirm Supabase plan/region/backup tier and VPS address mode; Identity and
Postgres RPO/RTO; off-site backup destination; Coolify dashboard domain; build
location; verified Resend sender; and whether existing Supplier TinyDB data is
authoritative. No external operation may infer these values.
