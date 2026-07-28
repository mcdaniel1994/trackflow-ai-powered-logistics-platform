# Engagement 6.4 Phase Review Evidence — 2026-07-28

## Status

Phase 6.4 implementation and same-day local verification are complete under the owner-approved
reporting-reliability specification. On 2026-07-28 the owner explicitly:

- waived the 48-hour steady-state study, separate deployment resource study, every 48-hour
  post-change comparison, and the seven-day clean-run period;
- directed that each waived gate be recorded as **waived, not passed or executed**;
- approved the production executor swap from Prefect to direct SQL after same-day verification;
  and
- did not approve a resource-limit change or final Prefect removal.

The production Compose selection is prepared in this change, but the production deployment and
post-deployment path verification have not yet occurred. Prefect services, guards, backup, and
runtime dependencies remain intact as a rollback path pending a separate final removal approval.

## Local direct-executor slice

`data/pipelines/business_performance/direct_executor.py` implements
`RunExecutor(engine, claim, abort) -> RunMetrics` without importing Prefect. It preserves:

- the existing PostgreSQL queue, claim, lease-renewal, retry/backoff, finalization, stale recovery,
  advisory-lock, and heartbeat owners outside the executor;
- unconditional stage recording under claim-token CAS;
- abort checks before and after each stage;
- fixed-cutoff rollup computation and claim-token publication verification;
- the existing `PipelineStageError` safe code/type taxonomy; and
- three total attempts with 10-second delays only for the approved transient-connectivity
  allowlist.

`REPORTING_EXECUTOR` is an allowlisted lazy selector. Code defaults to `prefect`; local Compose
preserves that default, while production Compose selects `direct_sql` under the explicit owner
approval. In direct mode the worker does not run Prefect startup guards, poll Prefect health, or
reconcile Prefect flow runs. Queue heartbeats remain healthy because the selected in-process
executor is available; durable queue stale recovery remains unchanged.

## Local verification

| Gate | Result |
|---|---:|
| Executor/worker/CLI focused tests | 17 passed |
| Complete data test suite | 154 passed, 1 opt-in test skipped |
| Data coverage | 90.32% overall; direct executor 97% |
| Central API deployment-contract tests | 13 passed |
| Ruff | Passed |
| Strict mypy | Passed |
| Data + Central API package builds | Passed |
| Compose local + production render | Passed |
| Disposable 2× projected-volume SQL rollup gate | Passed |

The focused tests prove unconditional stage CAS without Prefect context, missing-claim refusal,
abort handling between stages, transient-only bounded retries, safe failure mapping, and identical
Prefect/direct rollup and weekly output at the same fixed cutoff.

The complete suite covers scheduled/manual dispatch, bounded retry/backoff, independent lease
renewal, claim-token loss, process-death/restart recovery at every stage, stale-lease recovery,
terminal-attempt behavior, and fixed-cutoff Prefect/direct publication parity.

The opt-in disposable PostgreSQL performance test loaded 2,120,000 source/event rows and retained
the approved budgets:

- full aggregate: 1.569 seconds;
- full publication: 1.717 seconds;
- regular 72-hour aggregate: 0.061 seconds;
- reconciliation: 1.019 seconds;
- report read: 0.038 seconds; and
- test-process peak RSS: 316,178,432 bytes, below 80% of the current 768 MiB worker limit.

This test measures the shared SQL rollup path used by both executors. The owner waived the
time-based measurement gates rather than treating this same-day evidence as a substitute.

## Remaining production gates

- Merge and deploy the approved direct-SQL selection.
- Verify the new worker heartbeat and reporting readiness after the deployment boundary.
- Exercise the approved production path to the extent separately authorized and record actual
  outcomes; local proofs are not represented as production exercises.
- Obtain separate explicit approval before removing Prefect services, guards, backup, or the
  runtime dependency.
- File the required Prefect retirement note only with the final approved topology change.
