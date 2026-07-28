# Engagement 6 Reporting Reliability (Phases 6.1–6.4) — Implementation Plan

**Status:** proposed for owner review
**Authority:** `docs/planning/remaining_planning/spec.md`
**Owner:** Cory McDaniel
**Scope:** reporting reliability only; Engagement 6.5 is independent and may run in parallel

## 1. Authority, boundaries, and working agreement

The approved specification is binding. It supersedes
`docs/planning/remaining_planning/important_considerations/2026-07-23-trackflow-reporting-reliability-implementation-plan.md`
where they differ; this plan adopts every deliberate departure in specification §9. In particular,
it does not add a separate reporting topology, a work pool, dirty-bucket tracking, a batched
historical backfill, legacy shadow reads, or the failed legacy transform as rollback support.

The implementation keeps the specification's four phase boundaries. After each phase, attach the
required evidence, run the complete quality gates, update the engagement-tracking documents, and
stop for written owner review and approval. Do not begin the next phase on an assumption of
approval. Production remains untouched except through the phase's separately approved deployment
and verification actions.

Standing constraints:

- migrations are additive; production uses forward fixes and never a destructive downgrade;
- never delete, archive, compact, or truncate `stock_entries` or `stock_exits`;
- `operations-feed`, `reporting-worker`, and `maintenance-worker` remain separate containers and
  failure domains;
- `reporting.pipeline_runs` remains the sole dispatch authority;
- preserve `/reporting/*` response compatibility, the six queue states, and public warehouse
  values `los_angeles` / `zaragoza`;
- do not modify `packages/shared/`, `packages/trackflow_auth`, Identity ownership, delivered brief
  content, or any Engagement 6.5 file;
- inventory existing worktree changes before each phase and stage only the approved phase files.

## 2. Required reading and repository baseline

This plan was prepared after reading the startup files, Engagement 6 brief, remaining-planning
precedence rules, both approved specifications, the database/telemetry/testing/error-handling/
observability/production-readiness standards, all runbooks required by specification §0.1, the July
23 originating plan, applicable `.agents/rules/`, and READMEs for the relevant Central API, data
pipeline, migration, Back Office, and scripts folders.

The repository currently confirms the specification's characterization:

- Back Office Docker health calls `/api/health`, which aggregates dependency readiness.
- Central API readiness combines database/schema/runtime/reporting-grant checks with reporting
  worker state.
- the deployment workflow polls the same aggregate and treats failure as rollback-worthy;
- the size guard imports `run_once` and can execute reporting inside `maintenance-worker`;
- queue lease, worker/progress staleness, feed interval, and watchdog values require the specified
  changes;
- Prefect is only the executor behind the existing `RunExecutor` contract; queue, schedule,
  claim/lease/retry/recovery, and publication authority already live elsewhere.

`services/central-api/.env.production-readonly.local` exists locally. Its contents must never be
printed, copied into evidence, or committed.

## 3. Ambiguities and apparent tensions to resolve explicitly

These are not silently filled in by this plan:

1. **Phase 6.3 numbering:** specification §6 labels its subsections 6.1–6.5. This plan treats them
   as 6.3.1–6.3.5; no scope change is intended.
2. **Feature/config names:** the rollup shadow flag, active-version flag, stale/disable flag,
   endpoint paths, and additive status field names are not fixed. Before coding each contract,
   record proposed names and compatibility behavior in the phase diff; do not change an existing
   public field's semantics.
3. **Persisted logs:** the spec requires a host path, rotation size/count, maximum age, hard byte
   ceiling, permissions, and maintenance enforcement but supplies no figures. Phase 6.1 must
   propose values against the measured 100 GB disk and obtain owner approval before production
   configuration. The maintenance worker may maintain the shared log mount, but may not execute a
   report.
4. **Notifications/alerts:** the Coolify notification destination and the seven-day observation
   alerts are required external capabilities, but provider/destination and evidence format are not
   named. Production rollout stops until the owner selects and configures them.
5. **Attempt termination:** an executor cannot write a termination row after an uncatchable
   SIGKILL. Define and test how stale-lease recovery closes that durable attempt as `lease_lost`
   without fabricating an exception class; confirm this interpretation at Phase 6.1 review.
6. **Migration downgrade wording:** §0.4 prohibits destructive downgrades while §5.4 requires
   downgrade tests. This plan runs downgrade mechanics only against disposable databases to prove
   migration behavior and prior-image compatibility. Production is never downgraded and retains
   additive tables on rollback. Owner approval of this plan confirms that reading.
7. **Existing weekly warehouse vocabulary:** rollups use `LA`/`ZGZ`, while the existing weekly
   schema and prior image may encode public values. The Phase 6.2 migration design must prove
   prior-image compatibility and place mapping at the response boundary without silently rewriting
   historical public semantics.
8. **Unproven platform behavior:** Traefik routing, Coolify deployment/out-of-deployment handling of
   unhealthy containers, and production inclusion of commit `fe430ab` remain evidence tasks. Do
   not predict their outcomes or claim health checks caused restarts/404s.
9. **Production fault injection:** stopping workers, withholding grants, breaking core
   dependencies, replacing containers, cutover, rollback drills, and Prefect removal are
   production-affecting. Each needs an explicit owner-approved target, window, expected impact,
   evidence plan, and recovery path; plan approval alone is not execution approval.

## 4. Mandatory entry step — read-only production rescan

This is the first implementation activity, before any code, migration, or configuration edit.

1. Record a clean redacted worktree inventory and the repository/image revision under inspection.
2. Load the existing gitignored read-only environment without echoing it. Open an explicit
   read-only transaction and verify `current_user`, `transaction_read_only`,
   `default_transaction_read_only`, `rolsuper = false`, `rolcreatedb = false`, and
   `rolcreaterole = false`.
3. Re-capture every specification §1.1 measure: PostgreSQL/Alembic versions, database and relevant
   table sizes/counts, exit split, telemetry counts, warehouse split, ingest rate/outage pattern,
   weekly rows, pipeline-run outcomes/stages/metrics, worker heartbeat/orchestrator health,
   connections, and extensions.
4. Re-run the full-history entry/exit rollups and current extract with
   `EXPLAIN (ANALYZE, BUFFERS)`, retaining redacted plans and timings.
5. Never emit a DSN, password, connection string, query parameter containing a secret, customer
   identifier, or raw business row. Redact driver errors before preserving evidence.
6. Compare with the July 27 baseline and §7 budgets. **Stop and report before implementation** if
   volume moved by more than 25%, Alembic differs from `20260716_0010`, a query exceeds budget, the
   role is not provably read-only, or any evidence invalidates the approved design.

Deliverable: a dated, aggregate-only rescan appendix in the Phase 6.1 evidence package. It updates
facts, not architecture; a material change returns to the owner for a spec decision.

## 5. Phase 6.1 — Evidence preservation, availability decoupling, destructive-action safety

### 5.1 Implementation sequence

1. **Durable attempt model.** Add the additive migration and model/repository/schema support for
   `reporting.pipeline_run_attempts` exactly as specification §4.1.a defines, including unique
   `(run_id, attempt)`, descending start-time index, provenance, safe originating code/type, stage,
   timing, and retry outcome. Write one record on normal attempt termination and close abandoned
   attempts through token-safe stale recovery. Never store exception messages, SQL, payloads,
   customer identifiers, DSNs, or secrets. Extend reporting status with additive attempt history.
2. **Surviving diagnostics.** Emit structured stage start/complete, retry, timeout, lease-loss, and
   publication events correlated by run ID and attempt. Add `caplog` allowlist/forbidden-value
   tests. Implement the owner-approved host log path with least-privilege mode, bounded
   size/count/age/total bytes, and maintenance-worker retention. Preserve durable attempt/status
   evidence and GitHub deploy/smoke evidence independently of the container. Capture safe exit
   codes and Coolify events before replacement. Block rollout until a Coolify notification
   destination exists.
3. **Three health signals.**
   - add Next.js-only Back Office liveness and point `docker/backoffice.Dockerfile` at it;
   - make dependency readiness call Identity and Central API core readiness;
   - reduce Central API core readiness to database, schema compatibility, and production runtime
     role validation;
   - move all reporting grants and worker/queue/staleness fields to a separate reporting
     verification endpoint;
   - make deployment core readiness the only rollback signal and record reporting verification as
     a separate non-rollback step.
4. **Timeout coherence.** Apply 300 s stage deadlines, 900 s lease, 1800 s watchdog, 60 s lease
   renewal, 10 s worker heartbeat, 60 s worker stale, and 180 s progress stale. Add a unit test
   reading configured values and asserting `300 < 900 < 1800`, `60 << 900`, and `10 << 60`.
5. **Single executor.** Remove `runner.run_once`/claim/execution/publication from
   `db_size_guard.run_reporting_checkpoint`. Maintenance may enqueue a checkpoint and observe
   durable state only. Prove only the reporting worker can claim runs and retain the database's
   single-active constraint.
6. **Size-guard safety.** Make failed, stale, or unconfirmed checkpoint state block reset; pause or
   slow the feed at 400 MB using `operations_feed_control`; require an explicit off-by-default
   owner control for any hard-limit reset; exclude all `reporting.*` artifacts; and set local and
   production normal feed defaults to 15 seconds. The immutable-ledger rule means the approved
   implementation must remove unattended ledger truncation; no reset is executed during this
   engagement without a separate explicit owner approval.
7. **Platform verification.** Execute §4.1.h as evidence gathering, recording commands, timestamps,
   versions, observations, and limitations in `backend-coolify-deployment.md`. Correct factual
   `[INF]` statements if evidence contradicts them; do not retrofit evidence to the spec.
8. Update business-performance, deployment, operations-feed, and telemetry runbooks plus the
   tracking documents required by `AGENTS.md`.

### 5.2 Tests and acceptance

Use disposable PostgreSQL and local Compose for migration upgrade/downgrade mechanics, attempt
finalization/exhaustion/stale recovery, safe logging, health separation, missing-grant isolation,
timeout ordering, one-claimer enforcement, size-guard refusal, soft pause, and 15-second cadence.
Run Central API and data Ruff/mypy/build/pytest with coverage; Back Office type-check/lint/build/
tests; and Identity quality gates because the spec's phase review requires them.

With separately approved production exercises, satisfy all specification §4.1.i criteria:
15-minute reporting-worker stop with zero unrelated 5xx/404 and no rollback; broken core dependency
does fail/rollback; missing reporting grant affects reporting verification only; forced failures at
each stage remain retrievable after replacement; persisted-log controls and content safety are
proved; only one claimant exists; destructive reset cannot run unattended; soft control and 15 s
feed work; timeout test passes.

**REVIEW GATE 6.1:** attach rescan, migration/test/coverage/build output, platform findings,
production evidence, log/notification configuration, size-guard evidence, documentation diff, and
protected/unrelated-file audit. Stop for written owner approval.

## 6. Phase 6.2 — Durable SQL hourly rollups, computed in shadow

### 6.1 Implementation sequence

1. Add the additive `reporting.hourly_activity_rollups` and singleton `reporting.rollup_state`
   migration exactly per §5.1. Do not add dirty buckets, backfill cursor/status, or alter/delete raw
   and weekly rows.
2. Implement independently aggregated SQL for entries, dispatches, losses, stockouts, and
   discrepancies; combine only aggregated results. Use UTC hours, canonical `LA`/`ZGZ`, compatible
   client FK semantics, a dense warehouse/client/week grid, and dispatch-only outbound/
   discrepancy denominators.
3. Capture one immutable cutoff at claim start. Every 12 hours, recompute completed hours since the
   last committed cutoff plus an unconditional trailing 72 hours. Upsert by the unique key and
   advance `rollup_state` only in the successful publication transaction protected by the existing
   advisory lock and claim verification. Keep manual POST refresh idempotent.
4. Use a reporting-session-only 60 s statement timeout; retain the Central API 15 s default.
5. Put shadow computation behind the explicitly documented off-by-default flag. Prefect still
   executes claims and served output remains byte-identical; no rollup-backed reads activate.
6. Populate attempt cutoff/scanned/written fields. Record the future dirty-bucket trigger: any
   mutable or back-dated source outside the trailing window.
7. Build a re-runnable exact raw-SQL reconciliation job and bounded reference fixtures. Compare
   source/warehouse/client/week counts and units independently, including dispatch/loss and
   discrepancy invariants. Do not compare to the empty legacy weekly table.

### 6.2 Tests and acceptance

Test UTC/ISO/year boundaries, zero dimensions, dispatch/loss separation, zero denominators,
mid-run cutoff exclusion, late arrivals, 72-hour recomputation, crash/idempotent rerun,
single-publisher behavior, migration constraints/indexes/prior-image compatibility, and disposable
downgrade mechanics. At current and at least 2× projected six-month volume, prove ≤60 s regular and
full-history runs, ≤30 s per aggregation, ≤2 s reads, and worker RSS ≤80% of limit.

Acceptance is exact reconciliation, all reference/migration/performance tests passing, feature flag
off, byte-identical served responses, and complete attempt metrics.

**REVIEW GATE 6.2:** attach SQL plans/timings, reconciliation report, migration compatibility,
tests/coverage/builds, flag proof, tracking/runbook updates, and scope audit. Stop for written owner
approval.

## 7. Phase 6.3 — Reconciled cutover with safe degradation

### 7.1 Implementation sequence

1. Re-run reconciliation at a fixed live cutoff. Only on exact success, populate the existing
   weekly table from hourly rollups and atomically mark the rollup version active.
2. Switch reads to weekly rows for completed weeks, hourly rollups for the current incomplete week,
   and weekly sums for longer ranges. Map internal `LA`/`ZGZ` to unchanged public values at the
   response boundary.
3. Remove the raw-row Python transform and R2 transform cache from the computation path; do not
   retain or reactivate them as rollback.
4. Implement explicit transient-connectivity classification and bounded inner retries only for the
   allowlist in §6.3. Statement/lock timeouts, integrity/grant/programming/type/serialization and
   unclassified errors propagate immediately with originating safe code/type. Prohibit blanket
   exception retries.
5. Extend status additively with cutoff, publication, current stage/progress, safe error/attempt,
   and current/stale state. Manual refresh only enqueues. Render last verified data with stale
   metadata or a truthful degraded state; reporting control-plane failure returns safe stable-code
   503 while unrelated routes stay functional.
6. Exercise both rollback modes: last verified snapshot explicitly stale, and computation disabled
   by flag. Neither mode downgrades schema or runs legacy code.
7. Deploy only after approval, publish the first successful production report, reconcile live data,
   then start the required seven-day observation with the specified alerts.

### 7.2 Acceptance and review

Require the first successful production publication, exact post-cutover reconciliation, read
budget, both rollback drills, forced control-plane outage with safe reporting 503 and zero unrelated
5xx/404, and a complete seven-day observation covering cadence/stage/retries/reconciliation/size/
route alerts.

**REVIEW GATE 6.3:** attach publication and cutoff evidence, reconciliation, API/UI compatibility,
rollback/outage evidence, seven-day alert history, quality gates, tracking/runbook updates, and
scope audit. Stop for written owner approval. Phase 6.4 cannot start before this seven-day window
passes and the owner approves.

## 8. Phase 6.4 — Measured re-budget and Prefect executor replacement

### 8.1 Measurement and controlled re-budget

1. Capture a 48-hour uninterrupted steady-state study spanning two reports, daily prune, and four
   size-guard ticks; separately measure every deployment; after each single limit change, capture a
   48-hour comparison.
2. Retain ≤60 s raw samples and summaries for per-container mean/peak CPU/RSS, peak-to-limit, OOMs,
   restarts; and host CPU/RSS/swap/load/disk, Docker events, and exit codes.
3. Apply the binding decision rule only: lower when peak ≤60% of proposed ceiling with zero OOMs;
   raise when peak ≥80% of current ceiling; otherwise leave unchanged. Use measured free host memory
   at peak, not declared-ceiling arithmetic.

### 8.2 Executor swap and retirement

1. Implement a direct SQL executor under the existing `RunExecutor(engine, claim, abort) ->
   RunMetrics` contract in the reporting-worker container. Keep schedule/manual/CLI enqueue,
   claims, lease renewal, queue retry/backoff, terminal transitions, stale recovery, advisory lock,
   claim-token publication verification, and worker heartbeat unchanged.
2. Preserve CAS stage recording, abort checks, `PipelineStageError`, and publication verification.
   Make stage-recording enforcement unconditional in production without Prefect context.
3. Recreate Prefect extract-task retry behavior as explicit bounded retries for only the approved
   transient-connectivity allowlist; do not consume a queue attempt for a classified transient
   extract blip.
4. At the same fixed cutoff, prove direct and Prefect executors produce identical rollups. After an
   approved production swap, exercise scheduled/manual execution, retry/backoff, lease renewal,
   worker-restart and stale-lease recovery.
5. Observe a seven-day clean-run period. **Do not remove Prefect before it completes.**
6. After the evidence and a separate owner-approved topology change, remove the specified Prefect
   services, guards, backup, and runtime dependency. Keep reporting-worker separate and retain
   nullable historical `pipeline_runs.prefect_flow_run_id`.
7. File a `docs/archive/` retirement note describing delivered Prefect architecture, reason,
   acceptance evidence, and git-history location. Update Compose, deployment and reporting
   runbooks/tracking without leaving unused runtime code.
8. Document database growth at 15 s cadence against thresholds; delete no ledger rows.

### 8.3 Acceptance and review

At ≥2× projected six-month volume, retain the §7.3 budgets. Require the 48-hour post-change study
to show the measured headroom gate, zero OOMs, no unexplained restarts; all non-Prefect dispatch/
retry/lease/recovery paths; identical output; retirement note; and growth trajectory.

**REVIEW GATE 6.4:** attach all three measurement-study series, per-change decisions, fixed-cutoff
comparison, seven-day clean run, production path exercises, performance results, removal/topology
evidence, retirement note, complete quality gates, tracking docs, and protected/unrelated-file
audit. Stop for final written owner acceptance.

## 9. Quality gates and documentation that apply after every phase

Run and record, as applicable:

- Central API and data Ruff, strict mypy, builds, pytest with preserved/improved coverage;
- Identity Ruff/mypy/build/pytest with coverage as required by the spec review gate;
- Back Office type-check, lint, build, Vitest, and risk-relevant Playwright flows;
- Compose rendering, migration compatibility, release-script tests, and safe failure-path tests;
- secret/PII absence assertions and `git diff --check`.

Update together: root `README.md` roadmap and “What's Been Built”,
`docs/briefs/README.md`, only the active brief's `## Status`, `CLAUDE.md` “Where New Engagement Code
Goes”, `memory-bank/progress.md`, the relevant deliverable README, and phase-relevant runbooks.
Do not rewrite protected stakeholder content. A phase commit, only after owner review, names the
engagement and phase and contains no unrelated worktree changes.
