# Business Performance Pipeline Operations

## Status and safety boundary

Repository implementation and production hardening are complete and locally verified. Credential
rotation, the GitHub Production migration secret, the first approved hardened deployment, and the
rollback drill remain owner actions. Do not bypass the GitHub Production reviewer gate. Never
paste database or R2 credentials into commands, source control, logs, screenshots, or chat.

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
| `prefect-db-backup` | `python /app/prefect_db_backup.py` | immediately, then every 24 h | read-only Prefect DB role; distinct `PREFECT_BACKUP_R2_*` token |

The dispatcher checks America/Chicago time and creates at most one scheduled request after 07:00
for each Dallas business date. Missed ticks recover on the next minute check. The PostgreSQL
queue and its lease/claim-token transitions remain authoritative. The private Prefect Server has no
ports, work pool, or dispatch authority and uses its own persistent PostgreSQL volume. Do not create
duplicate Coolify scheduled jobs.

## Local dry run

Use only the disposable local PostgreSQL on `127.0.0.1:55432`. R2 variables may remain unset; that
disables cache reuse without disabling the pipeline.

```bash
docker compose -f compose.yaml config --no-interpolate
docker compose -f compose.coolify.yaml config --no-interpolate
docker build -f docker/central-api.Dockerfile -t trackflow-central-api:phase-10 .
uv run --project services/central-api alembic -c services/central-api/alembic.ini upgrade head
uv run --project data python data/pipelines/pipeline.py
```

Inspect safe queue metadata only:

```sql
SELECT id, trigger_type, requested_at, started_at, finished_at, status, attempt,
       target_weeks, rows_loaded, error_code
FROM reporting.pipeline_runs
ORDER BY requested_at DESC
LIMIT 20;
```

Do not query or expose `cache_nonce`, connection strings, or cache credentials in operational
evidence.

## Manual and forced requests

Administrators use `POST /reporting/pipeline-runs` through the Back Office. A normal request
coalesces with an identical pending request. `force_refresh: true` supplies a one-use cache nonce and
therefore recomputes even when source content is unchanged. Requests accepted while another run is
active remain queued; they are not errors and never run concurrently.

Monitor `GET /reporting/pipeline-runs/latest`. A running row is healthy while its heartbeat renews
the lease. Only an expired lease is reclaimed. A stale worker whose claim token no longer matches
cannot publish or finalize.

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
distinct random value; the database initializer grants that role read-only access. Backups use
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
2. Enqueues and synchronously executes a checkpoint using the normal reporting queue, runner,
   advisory lock, lease, and claim-token protocol.
3. In one transaction, truncates `inventory_discrepancies`, `stockout_events`, `stock_exits`, and
   `stock_entries`; updates `reporting.source_ledger_state.last_reset_at`; and marks the reset week
   incomplete.
4. Reseeds a consistent ledger window, then re-enables the feed.

If the checkpoint fails or cannot claim its exact request, the reset still protects the Supabase
size limit. Every week in the recompute window is recorded in `reporting.incomplete_weeks` with
reason `reset_checkpoint_failed`. The dashboard and API must continue to label those weeks
incomplete; never delete the marker merely to make a report appear healthy.

For a planned reset, pause the feed and run/verify the pipeline in the first minutes after an ISO
Monday boundary. Confirm a successful checkpoint before invoking the guarded reset. This minimizes
the partial interval, but the reset week is still honestly marked.

## Retention, verification, recovery, and rollback

`business-event-prune` removes stockout and discrepancy occurrence rows older than the configured
26-week ISO boundary. It does not prune reporting rows or technical telemetry. Verify deletion
counts from the structured completion log; do not log event payloads or client identifiers.

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
- The rotated `MIGRATION_DATABASE_URL` is not yet stored in GitHub Production.
- The first hardened production run and rollback drill are not executed.
