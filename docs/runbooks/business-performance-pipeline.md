# Business Performance Pipeline Operations

> **Back Office trigger controls removed (final-polish 2.3, UI decision).** The Back Office no
> longer exposes "Run now" / "Force refresh"; the BFF no longer allowlists
> `POST /reporting/pipeline-runs`. Triggering is now scheduled and CLI/operational only. The Central
> API `POST /reporting/pipeline-runs` endpoint and the `reporting.pipeline_runs` queue are unchanged
> and remain the dispatch authority. The buttons were removed because they mutated real reporting
> state from a recorded/demoed UI; they drove real `reporting-worker` refreshes.

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
swap. No resource-limit change is approved. Never paste database credentials into commands, source
control, logs, screenshots, or chat.
`direct_sql` is the only executor: it runs inside `reporting-worker` against PostgreSQL and owns
the queue, heartbeat, lease, retry, and stale-recovery paths. The SQL path passes the disposable
2.12-million-row performance gate. The waived time gates are not represented as evidence. Local
evidence is recorded in `docs/planning/engagement-6.4-phase-review-2026-07-28.md`.

**Prefect was retired in August 2026** after the owner approved removal; the six orchestration
containers and their dedicated database are gone from both Compose files. See
`docs/archive/prefect-orchestration-retirement.md` for what it delivered, why it was retired, and
which environment variables can now be deleted from Coolify.

The weekly report and `reporting.pipeline_runs` queue in TrackFlow PostgreSQL are the business
system of record.

## Runtime topology and schedule

| Service | Command | Internal schedule | Secrets |
|---|---|---|---|
| `reporting-worker` | `python -m pipelines.business_performance.worker` | queue poll 5s; heartbeat write 10s; dispatcher 60s | runtime `DATABASE_URL` |
| `maintenance-worker` | `python -m scripts.maintenance_worker` | size guard 15m; prune 02:15 America/Chicago | runtime `DATABASE_URL` |

The queue poll is read-only in steady state. The heartbeat row has a single writer — the 10 s beat
— plus a write-through on an orchestrator-health transition. Do not reintroduce a per-poll
heartbeat write: it was the largest single source of database write volume in production.

With `REPORTING_HOURLY_ROLLUPS_ENABLED=false` (the default), the dispatcher preserves the existing
single 07:00 America/Chicago request and served reports remain unchanged. When the reviewed shadow
flag is enabled, it uses idempotent 07:00 and 19:00 cadence slots. Missed ticks recover on the next
minute check. The PostgreSQL
queue and its lease/claim-token transitions are authoritative. Do not create duplicate Coolify
scheduled jobs.

## Local dry run

Use only the disposable local PostgreSQL on `127.0.0.1:55432`.

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
- `unavailable`: the worker heartbeat is stale or missing.

### Operator triage

For `unavailable`, confirm `reporting-worker` container health, then inspect only fixed-token
worker logs. Leave requested rows queued; do not run a
second worker or manually change status. Restore the dependency and verify `orchestrator_healthy`
returns true before work is claimed.

For `stuck`, record the run ID, attempt, `current_stage`, `stage_started_at`, and safe error code.
Do not extend the lease or edit the claim token. If the hard watchdog has not already restarted the
worker, restart only `reporting-worker`; PostgreSQL releases the advisory lock and the stale sweep
returns the row to `retryable`.

For retry exhaustion (`failed` after attempt 5), the parent row reports
`MAX_ATTEMPTS_EXCEEDED`; use the fifth `reporting.pipeline_run_attempts.error_code` to diagnose the
originating failure. Confirm readiness, then have an administrator create a new request. Never reset
`attempt` or recycle the failed row. `ORCHESTRATION_FAILED`, `INTERNAL_FAILED`,
`DB_UNAVAILABLE`, and `LOCK_UNAVAILABLE` are retryable before exhaustion; validation failures
require a corrected request.

## Resource limits and external gates

Repository limits remain provisional: reporting worker 768 MiB, maintenance worker 512 MiB. Do not
lower or claim these as production-tuned from local idle readings. Retiring Prefect returned the
512 MiB server, 256 MiB orchestration database, and 128 MiB backup service reservations to the
host. Production release still requires the approved 24-hour soak,
active-run per-process RSS/duration evidence, the deliberate slow-run renewal gate, and 48-hour
post-release memory sampling with at least 30% VPS headroom. Tune one service at a time from p99
evidence and repeat the acceptance suite.

Local idle snapshot on July 15, 2026 (Docker Desktop, not production): reporting worker 118.4 MiB.
This is only a reproducible baseline; it does not satisfy active-run, soak, VPS, or p99 evidence
gates.

The local database-backed crash matrix deliberately terminates a spawned worker process during
each of `extract`, `transform`, and `load`. Every case verifies PostgreSQL releases the advisory
lock, rolls back the uncommitted reporting write, and moves the expired run to `retryable` with
`STALE_ABANDONED`; separate claim-token tests reject zombie publication.

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
- the daily prune and size guard complete without sensitive output.

If worker behavior is unsafe, scale the relevant Compose worker to zero. Previous successful
reporting rows remain readable when a later run fails. Prefer a forward fix. The workflow restores
the prior immutable image automatically after deploy/readiness failure and never downgrades the
database.

## Known gaps

- Phase 6.3 rollback drill two was waived by owner exception and was not executed. Drill one passed
  without changing snapshot lineage or queueing unexpected work. The immutable-image rollback
  drill remains unexecuted.
- The persisted reporting-log settings are owner-approved and repository-wired; production
  permissions/retention and the Coolify notification destination still require live verification.
