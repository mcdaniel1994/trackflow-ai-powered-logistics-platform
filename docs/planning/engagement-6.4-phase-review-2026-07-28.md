# Engagement 6.4 Phase Review Evidence — 2026-07-28

## Status

Phase 6.4 has started locally under the owner-approved reporting-reliability specification. The
production executor remains Prefect-backed. No production executor swap, resource-limit mutation,
or Prefect topology removal has occurred.

The required 48-hour steady-state study, separate deployment studies, 48-hour post-change
comparisons, production path exercises, and seven-day clean-run period have **not started**. No
time-based evidence is compressed, inferred, or represented as complete.

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

The production worker still imports `prefect_executor`; the direct executor is deliberately
unselected pending separate production-swap approval.

## Local verification

| Gate | Result |
|---|---:|
| Direct-executor focused tests | 17 passed |
| Complete data test suite | 150 passed, 1 opt-in test skipped |
| Data coverage | 90.42% overall; direct executor 97% |
| Ruff | Passed |
| Strict mypy | Passed |
| Data package build | Passed |
| Disposable 2× projected-volume SQL rollup gate | Passed |

The focused tests prove unconditional stage CAS without Prefect context, missing-claim refusal,
abort handling between stages, transient-only bounded retries, safe failure mapping, and identical
Prefect/direct rollup and weekly output at the same fixed cutoff.

The opt-in disposable PostgreSQL performance test loaded 2,120,000 source/event rows and retained
the approved budgets:

- full aggregate: 1.401 seconds;
- full publication: 1.523 seconds;
- regular 72-hour aggregate: 0.061 seconds;
- reconciliation: 1.019 seconds;
- report read: 0.036 seconds; and
- test-process peak RSS: 315,998,208 bytes, below 80% of the current 768 MiB worker limit.

This test measures the shared SQL rollup path used by both executors. A complete Phase 6.4 review
still requires end-to-end executor performance evidence at the specified volume, the production
measurement studies, approved production swap and path exercises, the seven-day clean run, and the
separately approved final topology removal.

## Remaining approval and time gates

- Start and retain the uninterrupted 48-hour steady-state raw series and summary.
- Measure each deployment separately from steady state.
- Make at most one approved resource-limit change at a time, followed by its own 48-hour
  comparison; apply only the 60%/80% rules.
- Obtain explicit approval before selecting the direct executor in production.
- Exercise scheduled/manual execution, retry/backoff, lease renewal, worker restart, and
  stale-lease recovery after that approved swap.
- Complete the seven-day clean-run period without compression or an unapproved exception.
- Obtain separate explicit approval before removing Prefect services, guards, backup, or the
  runtime dependency.
- File the required Prefect retirement note only with the final approved topology change.
