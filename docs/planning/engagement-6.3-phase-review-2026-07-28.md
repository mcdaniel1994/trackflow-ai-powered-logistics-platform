# Engagement 6.3 Phase Review Evidence — 2026-07-28

## Status

Phase 6.3 is implemented and deployed through additive Alembic revision `20260728_0013`.
The reconciled weekly cutover and controlled production rollout steps 1-6 have passed, including
rollback drill one. On 2026-07-28 the owner explicitly accepted Phase 6.3 as-is and approved
beginning Phase 6.4 as an exception to the remaining acceptance gates. Rollback drill two and the
required seven-day observation were **waived, not passed or executed**. This exception authorizes
Phase 6.4 to begin; it does not authorize a production executor swap, resource-limit mutation,
final Prefect topology removal, or a Phase 6.4 time-gate exception.

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

## Controlled production rollout

| Step | Result | Evidence |
|---|---|---|
| 1. Deploy cutover-off release | Passed | Immutable SHA `b834fcd8b81d4904bb10fffcee363c8ccee58e2e`; additive revision `20260728_0013` |
| 2. Verify baseline | Passed | Liveness and core readiness stayed healthy; reporting worker heartbeat and Prefect health were current |
| 3. Enable reconciled cutover | Passed | `REPORTING_ROLLUP_CUTOVER_ENABLED=true`, computation enabled, stale override false |
| 4. Controlled production run | Passed | Run `f0c53414-7c0e-4a57-b456-0cf632ad2698`, attempt 1, succeeded |
| 5. Reconciliation and read budgets | Passed | 106,643 source rows, 432 hourly rows, six report rows; exact reconciliation and approved read budgets passed |
| 6. Rollback drill one | Passed | Safe 503 without Prefect, explicit stale snapshot serving, unrelated-route isolation, and full restoration verified |
| 7. Rollback drill two | Waived by owner exception | Not started or executed; no passing evidence exists |
| 8. Seven-day observation | Waived by owner exception | Not started or executed; no observation evidence exists |

### Production snapshot and run

- The active source cutoff is `2026-07-28T20:00:00Z`.
- The active snapshot publication time is `2026-07-28T20:27:22.505196Z`.
- The successful run finished at `2026-07-28T20:27:24.481784Z` with one durable attempt,
  106,643 rows extracted, 432 rows transformed, and six rows published.
- The authenticated Back Office serves the six-row verified snapshot and labels the active week
  incomplete because the source ledger reset mid-week.

### Rollback drill one

The owner approved only rollback drill one. The drill stopped the production Prefect Server
container while leaving the application and reporting worker running.

- The worker heartbeat remained current while its orchestrator status changed to unhealthy.
- Authenticated report reads and a normal manual refresh both returned HTTP 503 with
  `REPORTING_CONTROL_PLANE_UNAVAILABLE`.
- `/api/health/live` and `/api/health/ready` remained HTTP 200. The Back Office landing,
  inventory, telemetry, carrier scoring, incidents, suppliers, talent, and profile routes all
  remained HTTP 200, with no unrelated 5xx or 404 response.
- With only `REPORTING_FORCE_STALE=true`, the report returned HTTP 200 with six rows, state
  `stale`, and the unchanged cutoff/publication metadata above. The Back Office explicitly labelled
  the result as a stale verified snapshot.
- Prefect Server was restored, then only the production stale override was returned to `false`.
  Preview remained `false`.
- Normal release deployments before and after the flag change used the same immutable SHA.
  GitHub Actions runs
  [30399438040](https://github.com/mcdaniel1994/trackflow-ai-powered-logistics-platform/actions/runs/30399438040)
  and
  [30400067885](https://github.com/mcdaniel1994/trackflow-ai-powered-logistics-platform/actions/runs/30400067885)
  passed their migration, deployment, liveness, readiness, and separate reporting checks. Their
  image-rollback steps were skipped.
- Final read-only database verification found migration `20260728_0013`, a healthy orchestrator
  with a two-second worker heartbeat, zero running or queued/retryable work, the same active
  cutoff/publication, and the same successful run with exactly one attempt. This proves the drill
  neither queued unexpected work nor reactivated the legacy transform.
- Final operator verification showed `LIVE`, `IDLE`, the same six-row verified source snapshot,
  and the same cutoff/publication. Both stale-override records were `false`.

## Owner acceptance exception

The owner accepted Phase 6.3 as-is on 2026-07-28 and approved beginning Phase 6.4. This is a
recorded exception to the normal gate requiring passing evidence for steps 7-8. Rollback drill two
and the seven-day observation remain unexecuted and must never be described as passed.

The exception does not broaden production authority. The Phase 6.4 production executor swap,
resource-limit mutations, final Prefect topology removal, and any request to shorten or waive
Phase 6.4 measurement or observation windows require separate explicit owner approval.
