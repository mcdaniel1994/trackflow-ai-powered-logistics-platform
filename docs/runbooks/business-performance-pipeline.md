# Business Performance Pipeline Operations

> **Back Office trigger controls removed (final-polish 2.3, UI decision — not a Prefect
> consequence).** The Back Office no longer exposes "Run now" / "Force refresh"; the BFF no longer
> allowlists `POST /reporting/pipeline-runs`. Triggering is now scheduled and CLI/operational only.
> The Central API `POST /reporting/pipeline-runs` endpoint and the `reporting.pipeline_runs` queue are
> unchanged and remain the dispatch authority. The buttons were removed because they mutated real
> reporting state from a recorded/demoed UI, **not** because Prefect is unused — Prefect is still
> deployed, and in direct-SQL mode those buttons drove real `reporting-worker` refreshes.

## Status and safety boundary

Reporting-reliability Phase 6.1 is deployed through Alembic `20260728_0011`. It preserves a
sanitized row for every execution attempt, separates core readiness
from reporting verification, fixes watchdog/lease timing, and removes synchronous pipeline
execution from maintenance. The Phase 6.1 image and migration were deployed successfully on July
28. The owner directed the team to omit the remaining controlled acceptance exercises; that
exception is recorded without representing them as passed. The owner
approved the persisted-log defaults on 2026-07-28: 10 MiB rotation with nine backups, 14-day
retention, a 250 MiB directory ceiling, and a persistent `reporting-logs` volume mounted at
`/var/log/trackflow/reporting`. Do not bypass the GitHub
Production reviewer gate. Phase 6.2 durable hourly SQL rollups are deployed through
`20260728_0012` and enabled in production. The first 113,064-row full-history publication exceeded
the 60-second budget without committing partial state; the set-based correction was redeployed,
live-reconciled, and owner-accepted. Phase 6.3 is deployed through `20260728_0013`; its first
controlled run published six verified report rows, and the control-plane/safe-stale rollback drill
passed. The owner accepted Phase 6.3 as-is by explicit exception on July 28 and approved beginning
Phase 6.4. The computation-disable drill and seven-day observation were waived, not passed or
executed. The owner also waived the Phase 6.4 48-hour studies and seven-day clean run, explicitly
without passing or executing them, and separately approved the production direct-SQL executor
swap. No resource-limit change is approved; final Prefect removal remains separately owner-gated. Never
paste database or R2 credentials into commands, source control, logs, screenshots, or chat.
The Phase 6.4 direct executor and allowlisted selector are locally verified. Production Compose
selects `direct_sql`; code and local Compose retain Prefect as the default. In direct mode the
worker skips Prefect startup/health/orphan-flow coupling while preserving PostgreSQL queue,
heartbeat, lease, retry, and stale-recovery ownership. The shared SQL path passes the disposable
2.12-million-row performance gate. The waived time gates are not represented as evidence. Local
evidence and the remaining deployment-verification boundary are recorded in
`docs/planning/engagement-6.4-phase-review-2026-07-28.md`.

The weekly report and `reporting.pipeline_runs` queue in TrackFlow PostgreSQL are the business
system of record. The private Prefect Server and its dedicated PostgreSQL database retain only
orchestration history/recovery state. Cloudflare R2 recovery results, cache objects, and Prefect
database backups must never become business-work authority; missing R2 cannot change correctness.

## Runtime topology and schedule

| Service | Command | Internal schedule | Secrets |
|---|---|---|---|
| `reporting-worker` | `python -m pipelines.business_performance.worker` | queue 5s; heartbeat 10s; dispatcher 60s | runtime `DATABASE_URL`; optional `REPORTING_R2_*` |
| `maintenance-worker` | `python -m scripts.maintenance_worker` | size guard 15m; prune 02:15 America/Chicago | runtime `DATABASE_URL`; Prefect API URL only |
| `prefect-server` | `prefect server start` | always on | dedicated Prefect DB owner credential only |
| `prefect-postgres` | PostgreSQL 16 | always on | Prefect owner credential; creates read-only backup role |
| `prefect-postgres-bootstrap` | idempotent SQL/role bootstrap | once per deployment | Prefect owner and backup-role credentials |
| `prefect-db-backup` | `python /app/prefect_db_backup.py` | immediately, then every 24 h | read-only Prefect DB role; distinct `PREFECT_BACKUP_R2_*` token |

With `REPORTING_HOURLY_ROLLUPS_ENABLED=false` (the default), the dispatcher preserves the existing
single 07:00 America/Chicago request and served reports remain unchanged. When the reviewed shadow
flag is enabled, it uses idempotent 07:00 and 19:00 cadence slots. Missed ticks recover on the next
minute check. The PostgreSQL
queue and its lease/claim-token transitions remain authoritative. The private Prefect Server has no
ports, work pool, or dispatch authority and uses its own persistent PostgreSQL volume. Do not create
duplicate Coolify scheduled jobs.

PostgreSQL's native init directory runs only when the data directory is empty. TrackFlow therefore
bakes its init files into the pinned PostgreSQL image and also runs `prefect-postgres-bootstrap`
after database liveness on every deployment. The bootstrap uses `CREATE EXTENSION IF NOT EXISTS`
and create-or-alter role logic, so it repairs an incomplete existing volume and is safe to rerun.
Prefect Server and the backup service cannot start until it succeeds. Never replace this with
relative production bind mounts under `/docker-entrypoint-initdb.d`.

## Local dry run

Use only the disposable local PostgreSQL on `127.0.0.1:55432`. R2 variables may remain unset; that
disables cache reuse without disabling the pipeline.

```bash
docker compose -f compose.yaml config --no-interpolate
docker compose -f compose.coolify.yaml config --no-interpolate
docker build -f docker/central-api.Dockerfile -t trackflow-central-api:phase-10 .
uv run --project services/central-api alembic -c services/central-api/alembic.ini upgrade head
uv run --project data python data/pipelines/pipeline.py
uv run --project data python -m pipelines.business_performance.rollups \
  --start 2026-07-01T00:00:00Z --cutoff 2026-07-28T18:00:00Z
```

Inspect safe queue metadata only:

```sql
SELECT id, trigger_type, requested_at, started_at, finished_at, status, attempt,
       target_weeks, rows_loaded, error_code
FROM reporting.pipeline_runs
ORDER BY requested_at DESC
LIMIT 20;
```

Inspect attempt evidence separately; the parent row is current state, not the complete execution
history:

```sql
SELECT run_id, attempt, started_at, ended_at, stage, source_cutoff_at,
       rows_scanned, rollup_rows_written, retry_outcome, error_code
FROM reporting.pipeline_run_attempts
ORDER BY started_at DESC
LIMIT 50;
```

Do not query or expose `cache_nonce`, connection strings, or cache credentials in operational
evidence.

## Phase 6.2 shadow rollups

`reporting.hourly_activity_rollups` uses canonical `LA`/`ZGZ` codes and stores counts/units for
inbound movements, dispatch orders, losses, stockouts, and discrepancies. Discrepancy rate is
derived; it is never stored. Each completed-hour key also records the immutable source cutoff,
computation time, and pipeline version.

`reporting.rollup_state` is a singleton. The worker captures one completed-hour UTC cutoff,
recomputes from the prior committed cutoff plus an unconditional trailing 72 hours, upserts the
dense hour × warehouse/client grid, verifies the claim in the publishing transaction, and only
then advances the cursor. Manual week requests recompute the requested ISO week idempotently.

The rollup job raises `statement_timeout` to 60 seconds only for its own reporting transactions.
The Central API default remains 15 seconds. Any single aggregate exceeding 30 seconds, any
reconciliation mismatch, or any discrepancy count above dispatch count blocks activation.

Reconciliation compares raw entries, dispatches, losses, stockouts, and discrepancies independently
against rollup sums at one fixed cutoff. Its CLI prints aggregate status only. Do not include raw
rows or client identifiers in evidence. A mutable source or a back-dated source outside the
trailing 72-hour window is the trigger to design dirty-bucket tracking; do not silently widen the
window.

## Manual and forced requests

Administrators use `POST /reporting/pipeline-runs` through the Back Office. A normal request
coalesces with an identical pending request. `force_refresh: true` supplies a one-use cache nonce and
therefore recomputes even when source content is unchanged. Requests accepted while another run is
active remain queued; they are not errors and never run concurrently.

Monitor `GET /reporting/pipeline-runs/latest`. A running row is healthy while its heartbeat renews
the lease. Only an expired lease is reclaimed. A stale worker whose claim token no longer matches
cannot publish or finalize.

The API derives one `queue_state` used by the Back Office and readiness rules:

- `idle`: worker and orchestrator are healthy and no work is pending;
- `processing`: a running stage remains within its configured deadline;
- `queued`: requested work is waiting behind the current/next claim;
- `retrying`: the newest run is retryable and exposes its safe next-attempt time;
- `stuck`: a running stage exceeded its deadline, or an idle worker heartbeat is fresh while poll
  progress is stale;
- `unavailable`: the worker heartbeat is stale/missing or its last Prefect probe failed.

### Operator triage

For `unavailable`, confirm `reporting-worker`, `prefect-server`, and `prefect-postgres` container
health, then inspect only fixed-token worker/Prefect logs. Leave requested rows queued; do not run a
second worker or manually change status. Restore the dependency and verify `orchestrator_healthy`
returns true before work is claimed.

For `stuck`, record the run ID, attempt, `current_stage`, `stage_started_at`, and safe error code.
Do not extend the lease or edit the claim token. If the hard watchdog has not already restarted the
worker, restart only `reporting-worker`; PostgreSQL releases the advisory lock and the stale sweep
returns the row to `retryable`. Startup reconciliation closes the abandoned Prefect flow run.

For retry exhaustion (`failed` after attempt 5), the parent row reports
`MAX_ATTEMPTS_EXCEEDED`; use the fifth `reporting.pipeline_run_attempts.error_code` to diagnose the
originating failure. Confirm readiness, then have an administrator create a new request. Never reset
`attempt` or recycle the failed row. `ORCHESTRATION_FAILED`, `INTERNAL_FAILED`,
`DB_UNAVAILABLE`, and `LOCK_UNAVAILABLE` are retryable before exhaustion; validation failures
require a corrected request.

## R2 provisioning — owner action

GATE-8b remains open. When explicitly approved:

1. Create a private Cloudflare R2 bucket.
2. Create a token limited to Object Read & Write on that bucket only.
3. Add a lifecycle rule deleting `prefect-results/` objects after one day.
4. Inject `REPORTING_R2_BUCKET`, `REPORTING_R2_ENDPOINT`,
   `REPORTING_R2_ACCESS_KEY_ID`, and `REPORTING_R2_SECRET_ACCESS_KEY` into
   `reporting-worker` only.
5. Confirm those variables are absent from Central API, maintenance worker, Back Office, Identity,
   public website, and operations feed.

For Prefect database backups, create a second least-privilege token limited to the same private
bucket and the `prefect-backups/` prefix where provider policy supports prefix scoping. Inject only
`PREFECT_BACKUP_R2_BUCKET`, `PREFECT_BACKUP_R2_ENDPOINT`,
`PREFECT_BACKUP_R2_ACCESS_KEY_ID`, and `PREFECT_BACKUP_R2_SECRET_ACCESS_KEY` into
`prefect-db-backup`. Never reuse the reporting-worker token. Set `PREFECT_BACKUP_DB_PASSWORD` to a
distinct random value; the deployment bootstrap grants that role read-only access. Backups use
custom `pg_dump` format, run daily, retain seven days, and emit only fixed-token status logs. With
all backup R2 variables absent, the service logs `prefect_backups_disabled` and reporting continues.

If any value is missing, leave all four unset. Partial configuration fails closed; fully absent
configuration runs correctly with caching disabled.

## Prefect retention and restore verification

The maintenance worker deletes only terminal Prefect flow runs older than
`PREFECT_RUN_RETENTION_DAYS` (default 30) through the Prefect REST API. It has no Prefect database
credential. An API outage logs `maintenance_operation_failed operation=prefect_retention` and does
not repeat or block TrackFlow database retention.

Before production acceptance, perform one owner-approved restore drill without touching the live
volume:

1. Download one `prefect-backups/*.dump` object through a secure operator session into a temporary,
   access-restricted path. Do not print its URL, token, or contents.
2. Start a scratch PostgreSQL 16 container on an isolated network with a disposable credential and
   no host port.
3. Run
   `pg_restore --exit-on-error --clean --if-exists --no-owner --no-acl --dbname=<scratch-url> <dump>`
   from the pinned backup image. `--no-acl` keeps live role grants out of the isolated scratch DB.
4. Probe the scratch database with
   `SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='flow_run'`; require one row and
   record only the backup timestamp, image digest, table probe, and pass/fail.
5. Destroy the scratch container, volume, downloaded dump, and disposable credential. Never point
   `PREFECT_API_DATABASE_CONNECTION_URL` at the scratch database during the drill.

If the dedicated Prefect database is actually lost, stop `reporting-worker`, `maintenance-worker`,
and `prefect-server`; restore the newest verified dump into a new dedicated volume; run the same
table/extension probe; then start Prefect Server before clients. The TrackFlow queue remains intact,
so reconcile any `running` audit row through the normal stale-lease/orphan procedure rather than
creating work from Prefect history.

## Approval-gated Prefect upgrade

Prefect server/database changes are independent infrastructure changes, not ordinary app releases.
They require owner approval and a maintenance window:

1. Confirm the proposed server release supports PostgreSQL and is the same major as the intended
   client. Add its exact image digest/version mapping to `KNOWN_SERVER_DIGESTS` in
   `data/pipelines/business_performance/prefect_version.py`; never use a floating tag. Both the
   `prefect-version-guard` container and the reporting worker's startup guard read that one mapping,
   so an unlisted digest fails closed in both.
2. Produce and verify a fresh `prefect-backups/` dump. Record current server image digest, client
   lock version, database size, and `/api/health` result.
3. Stop reporting and maintenance clients. Change only `PREFECT_SERVER_IMAGE` first and start
   `prefect-postgres` plus `prefect-server`. Prefect 3.7.8's observed `server start` path applies its
   schema migrations; for a future version, confirm that release's documented migration behavior
   before the window and use its explicit database-upgrade command if required.
4. Require `/api/health` plus the fixed success tokens from both guards —
   `prefect_postgres_guard=complete` and `prefect_version_guard_complete`. The guards report but no
   longer gate startup, so read their logs rather than inferring success from the stack coming up.
   Then deploy any app image with the compatible Prefect client and start clients; each worker logs
   `reporting_worker_startup_guard=complete` once its own fail-closed check passes.
5. Run one manual report and verify correlation/stage fields. Keep `reporting.pipeline_runs` as the
   only work authority throughout.

If the server upgrade fails before clients start, restore the prior server digest and, only when
its schema is compatible, restart it. If its database migration is incompatible, restore the
pre-upgrade dump to a new dedicated volume. An app image rollback changes only
`TRACKFLOW_IMAGE_TAG`; it must never silently change or downgrade Prefect Server or its database.

## Resource limits and external gates

Repository limits remain provisional: Prefect Server 512 MiB, Prefect PostgreSQL 256 MiB,
reporting worker 768 MiB, and backup service 128 MiB. Do not lower or claim these as production-
tuned from local idle readings. Production release still requires the approved 24-hour soak,
active-run per-process RSS/duration evidence, the deliberate slow-run renewal gate, and 48-hour
post-release memory sampling with at least 30% VPS headroom. Tune one service at a time from p99
evidence and repeat the acceptance suite.

Local idle snapshot on July 15, 2026 (Docker Desktop, not production): Prefect Server 183.5 MiB,
Prefect PostgreSQL 73.72 MiB, reporting worker 118.4 MiB, and backup service 24.88 MiB. This is only
a reproducible baseline; it does not satisfy active-run, soak, VPS, or p99 evidence gates.

The local database-backed crash matrix deliberately terminates a spawned worker process during
each of `extract`, `transform`, and `load`. Every case verifies PostgreSQL releases the advisory
lock, rolls back the uncommitted reporting write, and moves the expired run to `retryable` with
`STALE_ABANDONED`; separate claim-token tests reject zombie publication and reconciliation tests
close Prefect runs orphaned by restart.

## Migration and runtime grants

Follow `supabase-migrations.md` for target confirmation, backup/disposable-data approval, migration
role usage, and rollback constraints. The approved workflow runs `central-api-migrate` from the
same immutable Central API image before changing Coolify's image tag. That command verifies the
migration identity, takes an advisory lock, upgrades to image head, applies current and future
table/sequence grants in `public` and `reporting`, and verifies them. The runtime role must not
have `CREATE` on either application schema and must never receive the migration credential.

## Reset checkpoint and incomplete weeks

At the database hard limit, the size guard:

1. Pauses the operations feed through its durable kill switch.
2. Prunes telemetry and refuses any destructive action by default.
3. Requires the owner to keep the feed paused and write the exact one-shot control note
   `owner-approved-db-size-reset`. The guard atomically consumes that note before checkpoint work;
   it cannot authorize a later run.
4. Enqueues a checkpoint and only observes the normal reporting worker. Maintenance never claims
   or executes pipeline work.
5. Only after that exact run succeeds, truncates the disposable source ledger in one transaction,
   updates `reporting.source_ledger_state.last_reset_at`, records the incomplete reset week, reseeds,
   and re-enables the feed.

A failed, stale, missing, or unconfirmed checkpoint blocks truncation and leaves the feed paused.
Repair reporting and obtain a fresh owner approval; never edit a run, reuse a consumed approval, or
delete an incomplete-week marker to make a report appear healthy.

## Retention, verification, recovery, and rollback

`business-event-prune` removes stockout and discrepancy occurrence rows older than the configured
26-week ISO boundary. It does not prune reporting rows or technical telemetry. Verify deletion
counts from the structured completion log; do not log event payloads or client identifiers.

The worker mirrors its existing safe structured logs to
`/var/log/trackflow/reporting/reporting-worker.log` on the persistent `reporting-logs` volume, with
10 MiB rotation and nine backups. Daily maintenance mounts the same volume and enforces a
14-day/250 MiB directory cap. The image creates the directory as UID 10001 with mode `0750`; the
worker creates the file with mode `0640`. The path is not exposed over HTTP. Production acceptance
must still prove these ownership, rotation, retention, and byte-limit controls on the deployed
host and verify delivery through a configured Coolify notification destination.

After the approved production deployment, verify:

- dispatcher creates one scheduled request for the Dallas date after 07:00;
- runner reaches `succeeded`, with a recent heartbeat while running;
- `/reporting/weekly-warehouse-client-performance` and the Back Office show the same week;
- incomplete weeks are prominently badged;
- only `reporting-worker` has `REPORTING_R2_*`; only `prefect-db-backup` has
  `PREFECT_BACKUP_R2_*` and the read-only Prefect DB credential;
- the daily prune and size guard complete without sensitive output.

If worker behavior is unsafe, scale the relevant Compose worker to zero. Previous successful
reporting rows remain readable when a later run fails. Prefer a forward fix. The workflow restores
the prior immutable image automatically after deploy/readiness failure and never downgrades the
database. R2 objects are disposable and may be deleted without a database rollback.

## Known gaps

- Reporting-result and backup R2 credentials are not provisioned; the verified absent-R2 path is
  non-blocking.
- The production Prefect restore drill is not executed.
- Phase 6.3 rollback drill two was waived by owner exception and was not executed. Drill one passed
  without changing snapshot lineage or queueing unexpected work. The immutable-image rollback
  drill remains unexecuted.
- The persisted reporting-log settings are owner-approved and repository-wired; production
  permissions/retention and the Coolify notification destination still require live verification.
