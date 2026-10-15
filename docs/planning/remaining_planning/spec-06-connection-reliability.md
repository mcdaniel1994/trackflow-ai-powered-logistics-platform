# Engagement 6 — connection reliability correction

**Owner approval:** October 15, 2026; explicit request to implement the proposed plan.
**Status:** Backend Phase 1 reviewed and continuation approved by the owner October 15. Phase 2 dashboard recovery and release preparation implemented and locally verified; owner approved commit/push after final review. Production unchanged.

## Evidence and objective

Supavisor logged repeated `EMAXCONNSESSION` / `ECHECKOUTFAILED` for the
`trackflow_runtime` / `postgres` / session pool during the October 15, 17:00–17:08
America/Chicago incident. The owner's Supabase investigation found 15 runtime sessions
(14 idle, one idle in transaction for approximately 22.5 hours), versus only 20 client
sessions against Postgres's separate 60-connection ceiling. Service attribution was unavailable.

Correct the shared connection budget and unnecessarily open lock transactions. Let successful
dashboard sections display independently and transient failures recover. The feed's missing
transaction completion is confirmed in code; attribution of the observed long production
transaction to that worker remains an inference.

## Phase 1 — backend connection management

| Consumer, one process/replica each | Retained size | Overflow | Maximum |
|---|---:|---:|---:|
| Central API SQLAlchemy | 3 | 0 | 3 |
| Operations feed | 2 | 1 | 3 |
| Reporting worker | 2 | 3 | 5 |
| Maintenance worker | 1 | 0 | 1 |
| Central API RFP checkpoints | 0 minimum | — | 1 |
| **Combined** | | | **13** |

Leave two of the 15 slots free. Count all processes, replicas, auxiliary clients and old/new
deployment overlap. Feed capacity includes its dedicated lock, business transaction and nested
diagnostic. Reporting supports its lock, computation, renewal, heartbeat and scheduler.

- Validate `DATABASE_POOL_SIZE`, `DATABASE_MAX_OVERFLOW` and
  `DATABASE_POOL_TIMEOUT_SECONDS` in both engine factories. Pin service-specific Compose
  values and a five-second checkout timeout. Preserve connect/statement/lock timeouts.
- Use a process-owned, maximum-one RFP checkpoint pool borrowing per database operation.
  Preserve autocommit, serialization, graph semantics and schema provisioning; close on shutdown.
  Declare the already-locked `psycopg-pool` directly and preserve LGPL attribution without upgrades.
- Persist the RFP business result and release its transaction before the independent best-effort
  trace checkout. Preserve ownership checks, safe 503 responses and trace failure isolation.
- Finish advisory-lock acquisition transactions while retaining session locks. Explicitly unlock
  during cleanup; invalidate uncertain physical sessions. Verify feed backend/lock ownership before
  every tick and stop before writing on loss. Preserve reporting CAS, leases and separate workers.
- Add fixed service labels and bounded startup/exhaustion diagnostics. Never log DSNs,
  credentials, SQL, payloads or raw driver messages. Do not automatically retry writes.

Verify pool/checkout limits, concurrency, safe failures, lock lifetime/cleanup/loss, feed diagnostic
emission, maintenance checkpoint/reset safety and RFP trace persistence. Run full Central API/data
lint, typing, builds, coverage and Compose/release checks. Run a ten-minute disposable local workload
with two authenticated dashboard clients and feed/reporting/maintenance/checkpoint work; require
runtime connections <=13, no idle-in-transaction lock holder, no exhaustion and successful reporting.
**Pause for owner review before Phase 2.**

## Phase 2 — dashboard recovery and release preparation

Change Operations Overview and Fulfilment details only. Use independent resource loading,
data/error/freshness, immediate rendering of successes and placeholders instead of false zeroes.
Retain stale successes with timestamps; clear data on date-range changes. Healthy polling is 20
seconds; network/502/503/504 retries use 2/4/8/16/30 seconds with +/-20% jitter, resetting on success.
One request per resource; pause while hidden, refresh on visibility, cancel on unmount/range changes.
Preserve auth refresh; do not transient-retry other 4xx. "Live" requires all latest attempts to
succeed with data under 60 seconds old; otherwise show connecting, partial or unavailable/retrying.

Response shapes stay unchanged; fetch helpers gain optional cancellation signals. Test partial
initial failure, stale retention, recovery/backoff, visibility, ranges, cancellation and empty data.
Complete Back Office gates and a mocked browser journey. Prepare immutable-image release,
client/topology preflight, replacement-overlap checks, post-deploy verification and image-plus-Compose
recovery. Update engagement tracking and runbooks without overwriting unrelated edits; pause for review.

## Authority and boundaries

This is the approved corrective extension to Engagement 6. It does not reopen delivered reporting
phases or apply their historical rescan revision/volume baselines to this incident. Existing
engineering/security standards and reporting business contracts remain authoritative.

Stop at a locally verified release candidate. Production rollout requires separate approval.
Keep Supavisor session mode and its current cap. No schema migration, role change, data repair,
paid AI call, production restart, session termination or deployment is authorized. Never use
the disposable-data waiver for RFP/agent business records.

Evidence: [connection-budget runbook](../../runbooks/connection-budget.md).
