# TrackFlow Reporting Reliability and Rollup Implementation Plan

> **Mandatory note for the next agent:** Before changing code, rescan the live Supabase database
> using the read-only connection in
> `services/central-api/.env.production-readonly.local`. Confirm the role remains read-only,
> inspect the current schema and Alembic revision, repeat the volume/performance queries described
> below, and update this plan if production has materially changed. Never place credentials or
> connection strings in this document, logs, commits, or command output.

## Summary

Replace the reporting pipeline's repeated raw-row Python transformation with durable PostgreSQL
hourly rollups computed every 12 hours. Backfill all existing Supabase data, distinguish dispatches
from losses, and build weekly reports from the stored rollups.

Reporting, Prefect, and cache failures must degrade reporting only. They must never make the Back
Office unhealthy, remove it from Traefik routing, or produce a site-wide 404.

Keep Prefect as a thin, isolated self-hosted coordinator. Supabase remains the authority for
business data, rollups, job state, retries, and recovery. R2 is removed from the reporting
computation path and retained only for optional backups or generated exports.

This plan supersedes the runtime/cache strategy in
`docs/planning/reporting-dedicated-prefect-architecture.md` where the two conflict.

## 1. Mandatory Production Rescan and Incident Capture

Before implementation:

- Load `DATABASE_INSPECT_URL` from the gitignored production read-only environment file. Verify
  `current_user`, `transaction_read_only`, and the effective role before querying.
- Capture:
  - Current Alembic revision, PostgreSQL version, database size, table sizes, indexes, constraints,
    triggers, and reporting schema.
  - Counts, quantities, minimum/maximum timestamps, daily rates, last-12-hour rates, and
    warehouse/client cardinality for entries, exits, stockouts, and discrepancies.
  - Exit counts split between `dispatch` and `loss`.
  - Existing weekly results, pipeline runs, attempts, heartbeats, stages, and underlying errors.
  - Read-only `EXPLAIN (ANALYZE, BUFFERS)` results for 12-hour, 48-hour, three-week, and
    longest-history grouped aggregation queries.
  - VPS memory, swap, CPU, disk, Docker events, container exit codes, restart policy, Coolify
    deployment history, and any OOM-kill evidence.
- Preserve failed-deployment evidence before another redeploy whenever recovery urgency permits.
  Do not diagnose the ten restarts as a health-check restart until container exit codes or Coolify
  events prove that.
- Compare results with the July 23, 2026 baseline:
  - 127,203 entries and 144,365 exits.
  - Approximately 36,000 combined movements per full day.
  - 130,312 dispatch exits and 14,053 loss exits.
  - 2,291 discrepancies, no stockouts, four clients, six SKUs, and six warehouse/client pairs.
  - 66 MB database size and an empty weekly reporting table.
  - Twelve failed runs, all ending as `MAX_ATTEMPTS_EXCEEDED`.
  - Three-week raw SQL aggregation completed in under 0.3 seconds.
- If volume has grown by more than 25%, schema/migration state changed, or query time exceeds the
  acceptance thresholds below, revise batch sizing before implementation.

## 2. Stabilize Availability and Preserve Failure Evidence

### Health-check separation

- Add a Back Office liveness endpoint that verifies only the Next.js process. Docker and Traefik
  must use this endpoint.
- Keep dependency readiness separate:
  - Back Office readiness checks Identity and Central API core readiness.
  - Central API core readiness checks only dependencies required for normal Back Office
    operations.
  - Reporting receives its own health/status endpoint.
- A failed, late, stopped, or unavailable reporting worker must leave the Back Office routable.
  The reporting page should show stale/degraded status and the last successfully published data.
- Use stage-specific reporting deadlines rather than the current conflicting 300-second readiness
  threshold and 1,800-second process watchdog:
  - Normal aggregation: 300 seconds.
  - Publication: 180 seconds.
  - Complete regular run: 900 seconds.
  - Historical backfill batches use separate progress-based monitoring and never affect core
    readiness.

### Durable attempt evidence

Add `reporting.pipeline_run_attempts` so terminal `MAX_ATTEMPTS_EXCEEDED` does not overwrite the
original failure:

- Store run ID, attempt number, stage, start/end timestamps, duration, source cutoff, rows scanned,
  rollup rows written, safe error code, exception type, and retry outcome.
- Keep detailed exceptions in structured server logs; store only sanitized fixed-token information
  in Supabase.
- Record container/build SHA and pipeline version on each attempt.
- Add structured stage-start, stage-complete, retry, timeout, and publication logs with correlation
  IDs.
- Configure bounded Docker log rotation and the existing Coolify notification destination. If
  Coolify has no notification destination configured, production rollout is blocked until one is
  supplied.
- Preserve deploy and smoke-test evidence in GitHub Actions so a Coolify redeploy cannot erase the
  only troubleshooting record.

## 3. Durable Rollup Model and Correct Report Semantics

Create the next additive Alembic migration after the production revision verified during the
rescan.

### Tables

- `reporting.hourly_activity_rollups`
  - Unique key: UTC `bucket_start`, normalized warehouse, and source-compatible `client_id`.
  - Store inbound movement count, inbound units, dispatch order count, dispatch units, loss
    movement count, loss units, stockout count, discrepancy count, source cutoff, computed
    timestamp, and pipeline version.
  - Do not store discrepancy rate; derive it from summed discrepancy and dispatch counts.
- `reporting.rollup_state`
  - Singleton state for current pipeline version, last successful cutoff, current backfill cursor,
    backfill status, last reconciliation, and last published week.
- `reporting.dirty_rollup_buckets`
  - Unique UTC hour plus warehouse/client identity requiring recomputation.
  - Populate transactionally for inserts, updates, or deletes affecting source activity, including
    historical corrections.
- `reporting.pipeline_run_attempts`
  - Durable attempt-level diagnostics described above.

Use additive migrations and preserve the existing weekly table and raw operational data. Do not
delete or reset source rows during this engagement.

### Computation rules

- Buckets are UTC hours represented by timezone-aware timestamps.
- ISO weekly reports retain the existing Monday-to-Monday UTC semantics unless the
  pre-implementation rescan proves the published API currently promises another timezone.
- Aggregate each source independently in SQL and combine the already-aggregated results. Never
  join raw entries directly to raw exits.
- Only `stock_exits.exit_type = 'dispatch'` contributes to outbound order throughput and
  discrepancy-rate denominators.
- Losses are stored separately and never counted as outbound orders.
- Generate a dense warehouse/client/week grid so zero-activity dimensions remain represented.
- Reports use:
  - Published weekly rows for complete historical weeks.
  - Hourly rollups for the current incomplete week.
  - Sums of weekly rows for longer historical periods.
- Remove the current R2 transformation cache and raw-row content-digest path from normal reporting.
  PostgreSQL rollups are the durable cache and survive worker crashes or redeploys.
- R2 may later hold database backups or downloadable exports, but its absence or failure must not
  block report computation or publication.

## 4. Incremental Processing, Backfill, and Prefect Isolation

### Regular 12-hour run

- Schedule at 00:10 and 12:10 UTC.
- Capture one immutable `source_cutoff_at` at run start and process only events with timestamps
  before that cutoff.
- Recompute:
  - Every completed hour since the previous successful cutoff.
  - The preceding 48 hours to absorb ordinary late-arriving data.
  - Any older bucket recorded in `dirty_rollup_buckets`.
- Upsert rollups idempotently by their unique key.
- Update the cursor and clear processed dirty buckets only after rollup publication commits.
- Use a PostgreSQL advisory lock so only one regular or backfill writer can publish at a time.
- A crash before commit leaves the cursor and dirty records unchanged, allowing the next run to
  repeat safely.

### Existing-data backfill

- Take a fixed cutoff and identify source dates containing data.
- Process one UTC day at a time with a 100,000-source-row safety ceiling. If a day exceeds the
  ceiling, subdivide it into six-hour windows.
- Persist the completed date/window after each committed batch so a crash resumes from the last
  durable checkpoint.
- Backfill chronologically through the fixed cutoff while regular ingestion continues.
- After hourly backfill:
  - Reconcile raw and rollup totals by source, warehouse, client, and week.
  - Assert dispatch and loss totals independently.
  - Confirm discrepancies never exceed dispatch orders for any report dimension.
  - Populate the existing weekly table from verified hourly rollups.
  - Mark the rollup version active only after reconciliation passes.
- If reconciliation fails, retain the old publication path and data, record the exact mismatches,
  and do not activate rollup-backed reports.

### Thin Prefect deployment

Create an isolated reporting Coolify resource containing:

- One digest-pinned Prefect server, initially limited to 0.25 CPU and 512 MiB.
- A dedicated persistent Prefect PostgreSQL service, initially limited to 0.25 CPU and 256 MiB.
- One reporting worker, initially limited to 0.5 CPU and 512 MiB.
- A single reporting work pool with concurrency one.
- No public Prefect route and no dependency from Back Office or Central API readiness to Prefect.
- Prefect coordinates schedules, flow visibility, and stage transitions only. Supabase performs
  aggregation and retains authoritative cursor, attempt, retry, and publication state.
- Prefect downtime causes delayed reporting followed by catch-up; it must not cause a Back Office
  outage.
- R2 is not required for Prefect task results or report correctness.

Deployment is blocked if the production rescan cannot demonstrate at least 2 GiB of sustained RAM
headroom after core services are running.

## 5. APIs, UI, Deployment, and Rollout

### Interfaces

- Preserve existing report-request and weekly-report response compatibility.
- Extend reporting status with:
  - `state`: idle, queued, processing, retrying, backfilling, stale, failed, or unavailable.
  - Last successful cutoff and publication time.
  - Current stage and progress.
  - Latest safe error code and attempt count.
  - Whether displayed results are current, stale, or being backfilled.
- Manual refresh queues an idempotent request. It must not perform raw computation in an HTTP
  request or force-refresh immutable historical buckets unnecessarily.
- Return safe `503` reporting responses when the reporting control plane is unavailable while
  keeping unrelated Back Office routes functional.

### Rollout order

1. Deploy durable attempt history, structured telemetry, and decoupled liveness/readiness.
2. Verify reporting can be stopped for at least 15 minutes without producing a Back Office 404.
3. Deploy additive rollup schema and incremental processor behind a disabled feature flag.
4. Run and reconcile the historical backfill.
5. Enable shadow reads comparing old weekly results with rollup-derived results.
6. Correct expected differences caused by excluding losses; investigate every other mismatch.
7. Switch reporting reads to rollups after reconciliation and performance gates pass.
8. Disable the raw Python transformation and R2 transformation-cache path.
9. Move reporting and Prefect into their separate Coolify resource.
10. Retain the old reporting code for one release as rollback support, then remove it after a
    stable observation period.

Rollback switches report reads back to the existing weekly table and disables new scheduling.
Rollup tables and attempt history remain intact; no destructive downgrade is required.

## Test and Acceptance Plan

- Unit tests cover UTC buckets, ISO-week boundaries, dispatch/loss separation, zero-activity
  dimensions, discrepancy rates, fixed cutoffs, dirty buckets, and idempotent upserts.
- Migration tests verify upgrade/downgrade behavior, indexes, uniqueness, triggers, and
  compatibility with the prior application image.
- Integration tests prove:
  - A worker crash during every stage resumes without duplicate rollups.
  - A late event within 48 hours is corrected automatically.
  - A historical event older than 48 hours creates and repairs a dirty bucket.
  - Concurrent scheduled/manual runs result in one publisher.
  - Prefect, R2, or the reporting worker being unavailable does not affect core readiness.
  - `MAX_ATTEMPTS_EXCEEDED` retains every underlying attempt error.
- Backfill reconciliation must exactly match raw inbound units, dispatch counts, loss counts,
  stockouts, and discrepancies at the fixed cutoff.
- Production-like performance tests use at least twice the projected six-month volume:
  - Regular 12-hour rollup finishes within 60 seconds.
  - Each historical batch finishes within 60 seconds.
  - Report reads finish within two seconds.
  - Reporting worker remains below 80% of its memory limit.
  - No aggregation statement exceeds 30 seconds.
- Deployment smoke tests verify core liveness, core readiness, reporting status, manual refresh,
  scheduled execution, last-known report rendering, and reporting-isolation behavior.
- Observe production for seven days before removing the fallback, with alerts for:
  - No successful rollup within 13 hours.
  - A stage exceeding its deadline.
  - Repeated retries or reconciliation failure.
  - Database size approaching the existing guard.
  - Back Office route failure independently of reporting status.

## Assumptions and Fixed Decisions

- Supabase remains the business system of record.
- Hourly buckets are durable; computation runs every 12 hours.
- The normal correction window is 48 hours, supplemented by durable dirty-bucket tracking.
- Historical backfill uses daily batches capped at 100,000 source rows.
- Prefect remains, but only as an isolated, self-hosted control plane.
- R2 is not a computation cache or recovery requirement.
- Reporting health is never part of Back Office liveness or Traefik eligibility.
- Raw source rows are retained until a separately approved retention engagement.
- Existing unrelated worktree changes must be preserved.
- Database, telemetry, testing, error-handling, observability, and production-readiness standards
  must be reread before implementation.
