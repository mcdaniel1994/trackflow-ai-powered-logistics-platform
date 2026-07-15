# Business Performance Pipeline Operations

## Status and safety boundary

Repository-side Phase 10 preparation is implemented and locally verifiable. Production migration,
grants, R2 provisioning, Coolify schedules, and the first production run remain Phase 11 owner
actions. Do not execute those actions without explicit approval naming the target database and
accepting the migration/recovery plan. Never paste database or R2 credentials into commands,
source control, logs, screenshots, or chat.

The weekly report in PostgreSQL is the business system of record. Cloudflare R2 is a private,
disposable transformation cache only; a missing or unavailable cache must not change report
correctness.

## Runtime topology and schedule

| Service | Command | Intended Coolify cron | Secrets |
|---|---|---|---|
| `reporting-dispatcher` | `.venv/bin/python -m pipelines.business_performance.dispatcher` | `*/5 * * * *` | `DATABASE_URL` only |
| `reporting-runner` | `.venv/bin/python -m pipelines.business_performance.runner` | `*/5 * * * *` | `DATABASE_URL` and optional `REPORTING_R2_*` |
| `business-event-prune` | `.venv/bin/python -m scripts.prune_business_events` | Daily | `DATABASE_URL`; retention defaults to 26 weeks |
| `db-size-guard` | `.venv/bin/python -m scripts.db_size_guard` | About every 15 minutes | `DATABASE_URL` and feed configuration |

The dispatcher checks America/Chicago time and creates at most one scheduled request after 07:00
for each Dallas business date. Missed ticks recover on the next `*/5` invocation. The PostgreSQL
queue and its lease/claim-token transitions remain authoritative; no Prefect server, Prefect Cloud,
or separate Prefect database exists.

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

## R2 provisioning — Phase 11 owner action

GATE-8b remains open. When explicitly approved:

1. Create a private Cloudflare R2 bucket.
2. Create a token limited to Object Read & Write on that bucket only.
3. Add a lifecycle rule deleting `prefect-results/` objects after one day.
4. Inject `REPORTING_R2_BUCKET`, `REPORTING_R2_ENDPOINT`,
   `REPORTING_R2_ACCESS_KEY_ID`, and `REPORTING_R2_SECRET_ACCESS_KEY` into
   `reporting-runner` only.
5. Confirm those variables are absent from Central API, dispatcher, Back Office, Identity, public
   website, prune jobs, and size guard.

If any value is missing, leave all four unset. Partial configuration fails closed; fully absent
configuration runs correctly with caching disabled.

## Migration and runtime grants — Phase 11 owner action

Follow `supabase-migrations.md` for target confirmation, backup/disposable-data approval, migration
role usage, and rollback constraints. After migration `20260714_0008`, connect as
`trackflow_migration` (the reporting-schema owner) and grant the runtime role access to the new
schema and objects:

```sql
BEGIN;
GRANT USAGE ON SCHEMA reporting TO trackflow_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA reporting TO trackflow_runtime;
ALTER DEFAULT PRIVILEGES IN SCHEMA reporting
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trackflow_runtime;
COMMIT;
```

Verify as the runtime role with read/write operations inside a transaction that is rolled back.
The runtime role must not have `CREATE` on `reporting` and must not receive the migration credential.

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

After enabling production schedules, verify:

- dispatcher creates one scheduled request for the Dallas date after 07:00;
- runner reaches `succeeded`, with a recent heartbeat while running;
- `/reporting/weekly-warehouse-client-performance` and the Back Office show the same week;
- incomplete weeks are prominently badged;
- only `reporting-runner` has R2 variables;
- the daily prune and size guard complete without sensitive output.

If dispatcher or runner behavior is unsafe, disable those Coolify schedules first. Previous
successful reporting rows remain readable when a later run fails. Prefer a forward fix. Roll back
the image to the prior immutable SHA only after disabling scheduled jobs; database downgrade is a
separate approval-gated action under `supabase-migrations.md`. R2 objects are disposable and may be
deleted without a database rollback.

## Known gaps

- GATE-8b R2 infrastructure is not provisioned.
- Production migrations/grants and schedules are not applied.
- The first scheduled production run and rollback drill are not executed.
