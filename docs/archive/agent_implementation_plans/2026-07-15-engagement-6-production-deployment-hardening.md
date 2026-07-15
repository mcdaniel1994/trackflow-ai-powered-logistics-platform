# Engagement 6 Production Deployment Hardening

## Status

Approved July 15, 2026. Repository implementation completed on branch
`codex/engagement-6-deployment-hardening`; production acceptance remains approval-gated.

## Objective

Replace manual reporting recovery with one reviewer-gated release flow that publishes immutable
images, migrates and verifies the database, deploys through Coolify, checks readiness and smoke
tests, and restores the previous application image when necessary. Move reporting and maintenance
scheduling into the normal Compose stack so Coolify needs no separate cron jobs.

## Ordered phases

1. Repair reporting failure propagation, safe diagnostic logging, writable `/tmp` Prefect state,
   worker heartbeat/status, and stale-worker Back Office behavior.
2. Deploy one always-on reporting worker and one maintenance worker; remove dispatcher, runner,
   prune, and size-guard profile services.
3. Add a fail-closed migration command and approval-gated immutable deployment with verified
   runtime grants and automatic image rollback; never downgrade the database.
4. Add liveness/readiness, Back Office dependency aggregation, release verification, runbooks,
   engagement tracking, and full release checks.

## Runtime decisions

- Reporting polls every 5 seconds, heartbeats every 10 seconds, is stale after 30 seconds, and
  checks the America/Chicago 07:00 dispatcher once per minute.
- Maintenance runs the database-size guard every 15 minutes and telemetry/business-event pruning
  daily at 02:15 America/Chicago.
- Workers use one replica, runtime database credentials, read-only filesystems, writable `/tmp`,
  resource limits, restart-on-failure, and graceful SIGTERM windows.
- PostgreSQL remains authoritative for advisory locking, leases, retries, idempotency, queue state,
  and single-run concurrency. Prefect remains an in-process orchestration library.
- R2 remains optional and private; fully absent configuration disables caching only.

## Migration and deployment decisions

- `MIGRATION_DATABASE_URL` exists only in the approval-protected GitHub Production environment and
  an inactive migration container, never a runtime service.
- `central-api-migrate` requires `trackflow_migration`, rejects `trackflow_runtime`, verifies
  non-elevated role attributes and database `CREATE`, takes an advisory lock, upgrades to image
  head, applies and verifies allowlisted current/default grants, and prints safe revision state.
- The single reviewer approval gates migration and deployment. Deploy/readiness failure restores
  the previous immutable SHA. Manual `image-rollback` skips migrations. Database downgrade is
  never automatic.
- Future database work follows expand/backfill/deploy/contract compatibility so the prior image
  remains a safe rollback target.

## Acceptance boundary

Disposable PostgreSQL role/migration tests, read-only worker image execution, Prefect success and
failure state, heartbeat/scheduling/SIGTERM behavior, Compose validation, mocked Coolify outcomes,
readiness failure modes, and package release checks must pass before merge. Production acceptance
then requires credential rotation, one approved deployment, Inventory/Operations/Reporting checks,
one successful manual report, schedule confirmation, and a controlled image-rollback drill.
