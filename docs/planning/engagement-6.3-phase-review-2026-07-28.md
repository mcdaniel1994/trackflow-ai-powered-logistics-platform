# Engagement 6.3 Local Review Evidence — 2026-07-28

## Status

Phase 6.3 is implemented and locally verified through additive Alembic revision
`20260728_0013`. It is **not production-accepted**. The cutover flag defaults off, no production
state has been changed, and Phase 6.4 remains blocked until the Phase 6.3 production exercises and
seven-day observation are complete.

Phase 6.2 is production-accepted. Its corrected production run committed 1,266 hourly rows at the
fixed `2026-07-28T19:00:00Z` cutoff, reconciled exactly across 12 dimensions in approximately
472 ms, served the rollup read in 39.5 ms, and recorded a 35.573-second successful durable attempt.

## Delivered

- The active executor always computes durable hourly SQL rollups. The raw-row Python transform and
  optional R2 transform cache remain available only as retired code and are unreachable from the
  executor.
- Candidate hourly publication, full-history exact reconciliation, complete-week publication, and
  active-version advancement occur in one repeatable-read transaction. Any mismatch or publication
  failure rolls back the whole candidate and preserves the prior verified snapshot.
- `reporting.rollup_state` records the active pipeline version, fixed source cutoff, and publication
  time only after reconciliation succeeds.
- Completed historical weeks read from `reporting.weekly_warehouse_client_performance`. The active
  incomplete week is summed from verified hourly rows at the active cutoff.
- The worker remains on the 07:00/19:00 America/Chicago cadence. The legacy daily executor is no
  longer selected.
- Inner SQL retries use an explicit transient-connectivity allowlist. Statement/lock timeouts,
  constraint/grant/programming failures, serialization failures, and unclassified exceptions
  propagate immediately to the existing durable queue retry machinery.
- `REPORTING_COMPUTATION_ENABLED=false` stops claims while preserving heartbeat and returns the
  stable `REPORTING_COMPUTATION_DISABLED` 503 from report reads and manual run requests.
- A forced control-plane outage returns `REPORTING_CONTROL_PLANE_UNAVAILABLE`. Explicit
  `REPORTING_FORCE_STALE=true` serves only the last verified snapshot, labelled stale with its
  cutoff and publication time; it never reactivates the legacy transform.
- Status responses add active state, cutoff/publication, current stage and row progress, latest
  safe error/attempt, and current/stale truth. The Back Office renders current, stale, and degraded
  states even when the report-data request safely returns 503.

## Local evidence

| Gate | Result |
|---|---:|
| Reporting pipeline integration suite | 93 passed, 1 opt-in performance test skipped |
| Central API suite | 176 passed |
| Back Office suite | 122 passed |
| Ruff and focused strict mypy | Passed |
| Back Office type-check, lint, and production build | Passed |
| Additive migration and idempotent production-migration contract | Passed |
| Local Compose rendering | Passed |

The integration fixtures prove:

- complete historical-week publication and hourly current-week reads;
- exact activation and active metadata;
- idempotent publication;
- candidate mismatch rollback preserving both the prior active metadata and prior hourly values;
- explicit transient retry and immediate non-transient propagation;
- computation kill-switch claim suppression;
- safe 503 behavior for computation disable and control-plane outage;
- explicit stale-snapshot serving;
- unchanged legacy response behavior while cutover remains disabled; and
- additive migration/schema constraints and production migration reruns.

## Controlled production rollout — approval required

No production step below is authorized by this local review.

1. Merge and deploy the immutable release with
   `REPORTING_ROLLUP_CUTOVER_ENABLED=false`,
   `REPORTING_COMPUTATION_ENABLED=true`, and `REPORTING_FORCE_STALE=false`.
2. Verify migration `20260728_0013`, public liveness/core readiness/reporting status, worker
   heartbeat/orchestrator health, and unchanged served weekly response behavior.
3. Enable `REPORTING_ROLLUP_CUTOVER_ENABLED=true` and redeploy once.
4. Queue one controlled run. Record its fixed cutoff, hourly and weekly row counts, attempt duration,
   active version/publication time, and first successful weekly response.
5. Re-run exact live raw-versus-hourly reconciliation at that active cutoff and measure the current
   and historical report reads against the approved budget.
6. Exercise rollback path one: force the reporting control plane unavailable, confirm report reads
   return the stable safe 503 and unrelated Back Office routes produce zero 5xx/404, then enable
   `REPORTING_FORCE_STALE=true` and confirm the prior cutoff/publication is served and labelled stale.
   Restore the control plane and set the flag false.
7. Exercise rollback path two: set `REPORTING_COMPUTATION_ENABLED=false`, confirm the worker
   heartbeats without claiming work and report reads/manual refresh return
   `REPORTING_COMPUTATION_DISABLED`, then restore the flag true.
8. Begin the required seven-day observation with alerts for missed cadence plus grace, stage
   deadline, repeated retry, reconciliation failure, database soft threshold, and independent Back
   Office route failure.

Phase 6.3 is accepted only after all eight steps have recorded passing evidence. Phase 6.4 cannot
begin before the seven-day observation and explicit owner acceptance.
