# Specification — Engagement 6 Reporting Reliability (Phases 6.1–6.4)

**Status:** approved for implementation planning.
**Scope:** Engagement 6 reporting reliability only.
**Audience:** the coding agent that will produce its own phased implementation plan from this document.
**Owner:** Cory McDaniel. Every phase ends in an owner review-and-approval pause.

---

## 0. How to use this document

### 0.1 Required reading before planning

1. `memory-bank/projectbrief.md`, `memory-bank/techContext.md`, `memory-bank/progress.md`
2. `AGENTS.md`, then `CLAUDE.md`
3. `docs/briefs/06-data-pipelines-telemetry.md`
4. `docs/standards/database-engineering-standard.md`, `telemetry-standard.md`, `testing.md`,
   `error-handling.md`, `observability.md`, `production-readiness.md`
5. `docs/runbooks/business-performance-pipeline.md`, `operations-feed.md`, `telemetry-inventory.md`,
   `supabase-migrations.md`, `backend-coolify-deployment.md`
6. `docs/planning/remaining_planning/important_considerations/2026-07-23-trackflow-reporting-reliability-implementation-plan.md`
   — the originating plan. **This specification supersedes it where they differ**, and the
   differences are deliberate and enumerated in §9.

### 0.2 Evidence classification

Every claim below is tagged. Do not promote a tag without new evidence.

| Tag | Meaning |
|---|---|
| **[RF]** | Confirmed repository fact — verified in checked-in code or configuration |
| **[PF]** | Confirmed production fact — verified against live Supabase through the read-only role |
| **[INF]** | Inference requiring verification |
| **[REQ]** | Requirement of this specification |
| **[OD]** | Owner decision, already made and recorded in §10 |

### 0.3 Non-goals

This specification does **not** cover, and implementation must not introduce:

- Sales forecasting (Engagement 6.5) or any machine-learning work. 6.5 is approved for the same
  delivery run but is delivered under its own specification and runs **in parallel**: it shares no
  code, no schema, no container, and no production surface with 6.1–6.4, and must not be sequenced
  behind them.
- Any Engagement 7–10 capability: vector stores, agent runtimes, MCP servers, real-time delivery,
  notification models, or their scaffolding.
- Any additional database, message broker, cache service, or scheduler.
- Any new folder, package, or service that is not required by a phase below.
- Ledger deletion, archival, or compaction (see §8.4).
- Changes to `packages/shared/`, `packages/trackflow_auth`, Identity's TinyDB ownership, or
  delivered stakeholder briefs.

### 0.4 Standing constraints

1. Migrations are **additive only**. No destructive downgrade is acceptable in any phase.
2. **No deletion of immutable inventory ledger rows** (`stock_entries`, `stock_exits`) under any
   circumstance in this engagement.
3. `operations-feed`, the reporting worker, and `maintenance-worker` remain **three separate
   containers with independent restart policies and independent failure domains**. Do not merge
   them, and do not create a new shared process.
4. `reporting.pipeline_runs` remains the **sole dispatch authority** throughout all four phases.
5. Existing unrelated worktree changes are preserved. Do not stage, commit, discard, or overwrite
   them.
6. Production is untouched unless the phase explicitly deploys, and every deployment is
   owner-approved.
7. After each phase: run type-check, build, lint, and tests for every touched package; meet the
   release gates in `docs/standards/production-readiness.md`; update the engagement-tracking docs
   named in `AGENTS.md` §3; then **stop and request review**.

---

## 1. Verified baseline

### 1.1 Production state, 2026-07-27 (read-only inspection) **[PF]**

| Measure | Value |
|---|---|
| PostgreSQL | 17.6 (Supabase), via the IPv4 Supavisor session pooler |
| Alembic revision | `20260716_0010` — matches repository head |
| Database size | 94 MB (66 MB on 2026-07-23; **+42% in four days**) |
| `stock_entries` | 195,638 — only **8 rows predate 2026-07-13** |
| `stock_exits` | 221,731 — dispatch 200,318 / loss 21,413 |
| `inventory_discrepancies` | 3,708 |
| `stockout_events` | 0 |
| `telemetry_events` | 9,025 (8,993 `inventory.dispatch.rejected`, 32 `api.access.denied`) |
| Warehouse split | `LA` 97,794 / `ZGZ` 97,844 |
| Ingest rate | ~17k entries + ~19k exits per day ≈ **36k movements/day** at a 5 s feed interval |
| Observed outage | 2026-07-21 and 07-22 volumes at 27% and 11% of baseline ≈ **~28 h feed outage** |
| `reporting.weekly_warehouse_client_performance` | **0 rows — reporting has never published** |
| `reporting.pipeline_runs` | **16 rows, 16 failed**, all terminal `MAX_ATTEMPTS_EXCEEDED` |
| Failing stage | `transform` on 15 runs; `extract` on 2026-07-24 |
| `rows_extracted` / `rows_transformed` / `rows_loaded` | NULL on every run |
| Worker heartbeat | fresh, `orchestrator_healthy = true` — the worker and Prefect are alive |
| `max_connections` | **60**, 24 in use, `trackflow_runtime` holding 10 |
| Extensions | `pg_stat_statements`, `pgcrypto`, `plpgsql`, `supabase_vault`, `uuid-ossp` |

### 1.2 Measured query cost **[PF]**

| Query | Result |
|---|---|
| Hourly rollup over **all** exits, grouped by hour × warehouse × client × exit_type | **210 ms**, 3,400 rows |
| Hourly rollup over **all** entries, grouped by hour × warehouse × client | **201 ms**, 1,701 rows |
| Current pipeline extract query (221,841 exit rows, server-side) | **672 ms** |

Full-history hourly rollup is therefore **~410 ms total, producing ~5,100 rows**. There is no
historical backfill problem, because there is effectively no history.

### 1.3 Mandatory pre-implementation rescan **[REQ]**

Before writing code, re-verify production through the existing read-only connection in
`services/central-api/.env.production-readonly.local`:

1. Confirm `current_user`, `transaction_read_only`, `default_transaction_read_only`, and that the
   role is neither superuser nor able to create roles or databases.
2. **Never** emit a connection string, password, or DSN into logs, command output, commits, or this
   document. Redact any driver error that could contain one.
3. Re-capture every measure in §1.1 and re-run the `EXPLAIN (ANALYZE, BUFFERS)` measurements in
   §1.2.
4. If row volume has moved by more than 25% again, or the Alembic revision differs from
   `20260716_0010`, or measured query time exceeds the §7 budgets, **stop and report** before
   implementing.

---

## 2. Failure characterization

### 2.1 Confirmed availability defect **[RF]**

`docker/backoffice.Dockerfile` declares `HEALTHCHECK` against `/api/health`. That route
(`uis/backoffice/app/api/health/route.ts`) calls Central API `/health/ready`, which runs
`check_readiness()` in `services/central-api/central_api/health.py`, which calls
`_check_reporting_worker()`. That check fails when the reporting worker heartbeat is older than
30 s, when `orchestrator_healthy` is not `true`, or when a running stage has exceeded its deadline.
`.github/workflows/deploy-production.yml` polls the same `/api/health` endpoint as its release gate
and automatically restores the previous image on failure **[RF]**.

**Characterization:** reporting readiness is a confirmed **availability defect and outage
amplifier**. Any reporting fault, of any origin, is escalated into container health-status
consequences and into deployment rollback. It converts a degraded report into a release-level
event.

**Precision required in all documentation and commit messages [REQ]:** a failing Docker
`HEALTHCHECK` marks the container **unhealthy**. It does not, by itself, restart the container.
What Coolify and Traefik do with an unhealthy container — routing eligibility, restart policy,
deployment interpretation — is **[INF]** and must be verified as a task in Phase 6.1 (§4.1.h). Do
not assert restart or 404 causation without that verification.

### 2.2 Unproven originating failure **[INF]**

The cause of the transform failures is **not established**, and implementation must not assert one.
`release_retryable()` in `data/pipelines/business_performance/queue.py` overwrites `error_code` with
`MAX_ATTEMPTS_EXCEEDED` and stores only a fixed safe summary, so every distinct failure presents an
identical signature **[RF]**. Container logs for the failing runs, for the July 15 startup failure,
and for the July 21–22 outage were not preserved.

What is known:

- Attempt 5 of run `8af0d51e` spent ~56 s in `extract` and ~11.5 min in `transform` before failing
  **[PF]**.
- Server-side extract SQL executes in 672 ms, so the ~56 s is client-side row materialization, not
  database time **[PF]**.
- The transform normalizes ~420k records three times per run and serializes them canonically twice,
  inside `cpus: "0.50"` / `memory: 768M` **[RF]**.
- Resource exhaustion, Prefect payload/timeout behaviour, and lease loss all terminate as
  *retryable* and are therefore indistinguishable in the durable record **[RF]**.

**Diagnosis is a deliverable of Phase 6.1, not a prerequisite for it.** Phase 6.1 makes the next
failure observable; it does not require the previous one to be explained first.

### 2.3 Correct model of Prefect's role **[RF]**

This model governs Phase 6.4 and must not be misstated.

| Concern | Owner |
|---|---|
| Schedule (07:00 America/Chicago) | `dispatcher.dispatch_tick` → `enqueue_scheduled` |
| Manual request | `POST /reporting/pipeline-runs` → `enqueue_manual` |
| CLI request | `enqueue_cli` |
| Atomic claim, attempt increment, target-week resolution | `claim_next` |
| Lease and renewal | `heartbeat`, `runner._renew_claim` |
| Retry, backoff, terminal transitions | `release_retryable`, `finalize_success`, `finalize_failure` |
| Stale-lease recovery | `recover_stale_runs`, swept by `dispatch_tick` |
| Single-publisher enforcement | `locks.advisory_lock` + `verify_claim_for_publication` |
| Worker liveness | `record_worker_heartbeat` |
| **Execution of an already-claimed run** | **Prefect, via `flows.prefect_executor`** |

Prefect owns only the last row. Phase 6.4 is a **replacement of `prefect_executor`** behind the
existing `RunExecutor` contract. It does **not** design a scheduler, a queue, a lease model, or a
recovery mechanism, all of which already exist and stay.

---

## 3. Canonical decisions

These are settled. Implementation applies them; it does not re-open them.

| ID | Decision |
|---|---|
| D-1 | Prefect is retired **only after** the direct SQL executor is verified in production and a 7-day clean-run period has elapsed (§7.4). |
| D-2 | Inner SQL retries apply **only to explicitly classified transient connectivity failures** (§6.3). |
| D-3 | Rollup cadence: **hourly buckets, execution every 12 hours, trailing 72-hour recomputation, manual refresh available** (§5.3). |
| D-4 | The synthetic operations feed runs at a **15-second** normal interval, with soft-threshold slow/pause (§4.1.g). |
| D-5 | Diagnostic evidence is preserved by a **host-persisted log path** plus **durable critical-path events**, both governed by §4.1.b. |
| D-6 | Resource measurement is three separate studies (§7.1). No limit changes outside that protocol. |
| D-7 | The release gate uses **core readiness excluding reporting**. Reporting verification is a separate, reported, **non-rollback** signal (§4.1.c). |
| D-8 | `LA` / `ZGZ` are the canonical internal warehouse codes. The existing public reporting values (`los_angeles` / `zaragoza`) are **preserved by boundary mapping** (§5.5). |
| D-9 | Agent, memory, MCP-audit, and workflow-approval records are **business data**; the disposable-data waiver does not extend to them. Stated as a contract in §8.3; no implementation in this engagement. |

---

## 4. Phase 6.1 — Evidence preservation, availability decoupling, destructive-action safety

No computation change. This phase makes the next failure observable, stops reporting from
amplifying into outages, and removes the unattended destructive path.

### 4.1.a Durable attempt history

Create `reporting.pipeline_run_attempts` in a new additive migration.

| Column | Purpose |
|---|---|
| `id` | Primary key |
| `run_id` | FK → `reporting.pipeline_runs.id`, `ON DELETE CASCADE` |
| `attempt` | Attempt number within the run |
| `stage` | `extract` \| `transform` \| `load` \| `orchestration` \| NULL |
| `started_at`, `ended_at`, `duration_ms` | Attempt timing |
| `source_cutoff_at` | Immutable cutoff used by the attempt (NULL before Phase 6.2) |
| `rows_scanned`, `rollup_rows_written` | Volume, NULL where not applicable |
| `error_code` | The **originating** safe code, never `MAX_ATTEMPTS_EXCEEDED` |
| `error_type` | Exception class name only |
| `retry_outcome` | `retried` \| `exhausted` \| `failed` \| `lease_lost` \| `succeeded` |
| `pipeline_version`, `build_sha` | Provenance |

Requirements **[REQ]**:

1. One row per attempt, written on attempt termination.
2. A terminal `MAX_ATTEMPTS_EXCEEDED` on `pipeline_runs` **must never** overwrite or obscure the
   originating attempt error. `MAX_ATTEMPTS_EXCEEDED` never appears in `pipeline_run_attempts.error_code`.
3. Only sanitized, fixed tokens and exception class names are persisted. No exception messages, SQL,
   payloads, connection details, identifiers of end customers, or secrets.
4. Attempt rows survive the run's terminal transition and are readable through the reporting status
   surface.
5. Index on `(run_id, attempt)` unique, and on `(started_at DESC)`.

### 4.1.b Structured diagnostics that survive container replacement

Emit structured stage-start, stage-complete, retry, timeout, lease-loss, and publication log lines
with a correlation ID that ties log lines to `run_id` and `attempt`.

**Preservation [REQ] (D-5):** bounded `json-file` rotation is destroyed when a container is replaced
on redeploy, so it is not sufficient on its own. Implement both:

1. **Host-persisted log path** for the reporting worker, subject to all of:
   - **Rotation:** size-based with an explicit maximum file size and file count.
   - **Retention:** an explicit maximum age, enforced by the existing `maintenance-worker`
     schedule — not by an ad-hoc script.
   - **Disk limit:** a stated hard ceiling on total bytes for the log path, with the retention job
     enforcing it, and a documented figure against the 100 GB host disk.
   - **Permissions:** least-privilege ownership and mode; the path is not world-readable and is not
     served by any HTTP surface.
   - **Content safety:** the same secret- and PII-safe rules as the durable rows — no tokens,
     credentials, DSNs, request bodies, emails, client names, or end-customer identifiers. Add
     `caplog` tests asserting their absence, following the pattern already used in
     `services/identity/tests/`.
2. **Durable critical-path events** — `pipeline_run_attempts` (§4.1.a) plus the reporting status
   surface — so the reporting failure record survives regardless of log configuration.

Additionally: configure a Coolify notification destination (production rollout is blocked without
one), and preserve deploy and smoke evidence in GitHub Actions so a redeploy cannot erase the only
troubleshooting record. Capture container exit codes and Coolify deployment events before a
container is replaced.

### 4.1.c Three health signals

Replace the current two-endpoint arrangement with three distinct signals.

| Signal | Consumer | Contents | Effect on failure |
|---|---|---|---|
| **Back Office liveness** | `docker/backoffice.Dockerfile` `HEALTHCHECK`; Traefik routing eligibility | Next.js process responds — nothing else | Container marked unhealthy; downstream consequences per §4.1.h |
| **Core readiness (reporting excluded)** | `.github/workflows/deploy-production.yml` release gate | Identity reachable; Central API database reachable; schema revision compatible; **runtime role validated** | **Rollback trigger** |
| **Reporting verification** | Post-deploy step and operations | Reporting worker liveness, queue state, last successful cutoff, staleness, reporting-schema grants | **Reported only — never a rollback trigger** |

Implementation **[REQ]**:

1. Add a Back Office liveness route that verifies only the Next.js process. Repoint the Dockerfile
   `HEALTHCHECK` to it.
2. Split `uis/backoffice/app/api/health/route.ts` into a liveness path and a dependency-readiness
   path. The dependency-readiness path calls Identity health and Central API **core readiness**.
3. **Split `_check_runtime_reporting_access` in `central_api/health.py`:**
   - **Core readiness keeps** runtime-role validation — in production, `current_user` must equal
     `settings.runtime_database_role`.
   - **Core readiness loses** every reporting-schema and reporting-table grant check. Those move
     **exclusively** to reporting verification.
   - Core readiness therefore consists of: `_check_database`, `_check_schema_compatibility`, and
     runtime-role validation. Nothing else.
4. Remove `_check_reporting_worker` from core readiness entirely.
5. Expose reporting state on its own endpoint, carrying: queue state, worker heartbeat age,
   orchestrator health, last successful cutoff, publication time, staleness, latest safe error code,
   attempt count, and reporting-schema/table grant status.
6. Point the deployment gate at core readiness. Add reporting verification as a **separate,
   non-rollback** post-deploy step that records its outcome as deployment evidence.

### 4.1.d Coherent timeout values

Adopt these exact values. The invariant is **stage deadline < lease < watchdog**, with renewal and
heartbeat intervals an order of magnitude below what they protect.

| Setting | Current | **Specified** | Rationale |
|---|---|---|---|
| Stage deadline (extract / transform / load, each) | 300 s | **300 s** | Retained; ample for SQL rollups, and truthfully breached by the legacy transform |
| Lease (`DEFAULT_LEASE_SECONDS`) | 600 s | **900 s** | Must exceed the stage deadline with margin; 15 renewal intervals of headroom |
| Hard run watchdog (`REPORTING_RUN_TIMEOUT_SECONDS`) | 1800 s | **1800 s** | Retained; strictly greater than the lease |
| Lease renewal interval (`REPORTING_HEARTBEAT_SECONDS`) | 60 s | **60 s** | 1/15 of the lease |
| Worker heartbeat interval | 10 s | **10 s** | Unchanged |
| Worker-stale threshold (`WORKER_STALE_AFTER`) | 30 s | **60 s** | 30 s is exactly three missed beats — too tight to distinguish a blip from an outage |
| Progress-stale threshold (`PROGRESS_STALE_AFTER`) | 120 s | **180 s** | Consistent with the 60 s worker-stale threshold |

Ordering check: `300 < 900 < 1800`; `60 ≪ 900`; `10 ≪ 60`. **[REQ]** Add a unit test asserting these
inequalities from the configured values, so a future change cannot silently break the ordering.

**Expected and acceptable side effect:** between 6.1 and 6.3 the legacy transform (~690 s observed)
exceeds the 300 s stage deadline and will be reported as `stuck`. That is truthful. Because
reporting no longer feeds core readiness, it has no availability or deployment consequence.

### 4.1.e Failure-domain isolation

Remove the in-process execution path from `db_size_guard.run_reporting_checkpoint`, which currently
calls `runner.run_once` and executes a full reporting run inside `maintenance-worker` **[RF]**.

**[REQ]** The maintenance worker may **request** a reporting checkpoint (enqueue) and **observe**
reporting state (read `pipeline_runs`, `worker_heartbeats`, `rollup_state`). It may not claim,
execute, or publish a reporting run. After this change exactly one process claims runs, verifiable
by test and by the single-active partial unique index.

### 4.1.f Runtime-role and grant verification move

Reporting-schema `USAGE` and per-table `SELECT, INSERT, UPDATE, DELETE` checks for
`weekly_warehouse_client_performance`, `pipeline_runs`, `pipeline_run_attempts`, `incomplete_weeks`,
`source_ledger_state`, and `worker_heartbeats` move out of core readiness and into reporting
verification (§4.1.c). A missing reporting grant must produce a clear, actionable reporting-verification
failure — and must not fail core readiness or trigger rollback.

### 4.1.g Destructive size-guard protection

Projected first hard-limit trigger is approximately mid-September 2026 at the pre-change ingest rate
**[INF, from §1.1]**, so this lands in the first phase rather than the last.

**[REQ]**

1. **Failed or stale checkpoint blocks unattended reset.** `db_size_guard` must not proceed to a
   destructive reset when the reporting checkpoint has failed, is stale, or cannot be confirmed.
2. **Soft-threshold ingest control.** At the soft threshold (400 MB) the synthetic operations feed
   **slows or pauses** through the existing `operations_feed_control` kill switch, instead of
   continuing to grow the database toward the hard threshold. Telemetry pruning continues.
3. **Destructive reset requires explicit owner approval.** No unattended `TRUNCATE` of
   `stock_entries`, `stock_exits`, `inventory_discrepancies`, or `stockout_events` under any
   condition. Gate it behind an explicit, off-by-default control that an owner sets deliberately,
   and log the refusal loudly when the hard threshold is reached without approval.
4. **Reporting artifacts are excluded from truncation** — `reporting.*` tables, including rollups and
   attempt history, are never truncated by the guard.
5. **Normal feed interval is set to 15 seconds** (D-4), reducing ingest to roughly a third of the
   current rate. `operations_feed_interval_seconds` default and the production value both change.

Ledger deletion, archival, and compaction remain out of scope (§8.4).

### 4.1.h Verification tasks (unproven behaviour)

**[REQ]** Verify and record, without asserting the outcome in advance:

1. What Traefik does with a container whose Docker health status is `unhealthy` — specifically
   whether it is removed from routing.
2. What Coolify does with an unhealthy container during and outside a deployment.
3. Whether the deployed production image includes commit `fe430ab`.

Record findings in `docs/runbooks/backend-coolify-deployment.md`. If verification contradicts any
`[INF]` statement in this specification, correct the specification rather than the evidence.

### 4.1.i Phase 6.1 acceptance

1. With the reporting worker stopped for **at least 15 minutes**: **zero unrelated Back Office 5xx
   or 404 responses**, the Back Office remains routable, and no deployment rollback is triggered.
   Reporting endpoints may return a safe, truthful `503` with a stable error code — that is correct
   behaviour, not a failure.
2. A deliberately broken **core** dependency (database unreachable, schema behind, wrong runtime
   role) **does** fail the release gate and does trigger rollback.
3. A missing reporting-schema grant fails **reporting verification only**.
4. A forced failure injected at each stage produces a retrievable `pipeline_run_attempts` row naming
   the stage and exception class, still retrievable **after the container has been replaced**.
5. Persisted logs demonstrate rotation, retention, the stated disk ceiling, correct permissions, and
   absence of secrets and PII under `caplog` assertions.
6. Exactly one process claims reporting runs.
7. The size guard cannot perform a destructive reset unattended; the soft threshold demonstrably
   slows or pauses the feed; the feed runs at 15 s.
8. The timeout-ordering test passes.

---

## 5. Phase 6.2 — Durable SQL hourly rollups, computed in shadow

Correct computation lands behind a flag. Nothing user-visible changes. Prefect still executes
claimed runs.

### 5.1 Schema (additive migration)

`reporting.hourly_activity_rollups`

- Unique key: UTC `bucket_start` × canonical `warehouse` × source-compatible `client_id`.
- Columns: `inbound_movement_count`, `inbound_units`, `dispatch_order_count`, `dispatch_units`,
  `loss_movement_count`, `loss_units`, `stockout_count`, `discrepancy_count`, `source_cutoff_at`,
  `computed_at`, `pipeline_version`.
- **Discrepancy rate is derived, never stored.**
- `client_id` carries the same FK semantics as the existing weekly table.
- Index supporting week-range reads.

`reporting.rollup_state` — singleton: `pipeline_version`, `last_cutoff_at`, `last_published_at`,
`last_reconciled_at`. No backfill cursor and no backfill status; there is no batched backfill (§5.4).

The existing weekly table and **all raw rows** are preserved.

### 5.2 Computation rules **[REQ]**

1. Buckets are UTC hours represented by timezone-aware timestamps.
2. Each source is aggregated **independently in SQL** and the already-aggregated results are
   combined. Never join raw `stock_entries` to raw `stock_exits`.
3. **Dispatch/loss correction:** only `stock_exits.exit_type = 'dispatch'` contributes to outbound
   order throughput and to discrepancy-rate denominators. Losses are stored separately and are never
   counted as outbound orders. This corrects a live defect: the current pipeline counts all 221,731
   exits as outbound orders, including 21,413 losses — a **9.7% overstatement** **[RF/PF]**.
4. A dense warehouse × client × week grid is generated so zero-activity dimensions remain
   represented.
5. ISO Monday-to-Monday UTC weekly semantics are retained unless the §1.3 rescan proves the
   published API currently promises another timezone.

### 5.3 Cadence, cutoffs, and idempotent publication (D-3)

1. **Hourly buckets; execution every 12 hours.**
2. One immutable `source_cutoff_at` is captured at run start; only events strictly before it are
   processed.
3. Each run recomputes every completed hour since the last successful cutoff, plus a **trailing
   72-hour window**, applied unconditionally.
4. **Manual refresh remains available** through the existing `POST /reporting/pipeline-runs` path
   and is idempotent.
5. Rollups are upserted by their unique key. The cursor in `rollup_state` advances **only after**
   publication commits.
6. The existing advisory lock plus `verify_claim_for_publication` inside the publishing transaction
   remain the single-publisher guarantee.
7. A crash before commit leaves the cursor unchanged; the next run repeats safely.
8. **Dirty-bucket tracking is deferred, not deleted.** The sources are append-only by design, so
   there is currently no path that dirties a historical bucket outside the trailing window. Record
   the trigger condition — introduction of any mutable or back-dated source — as the point at which
   dirty-bucket tracking becomes required. Do not build the table now.

### 5.4 Validation — reconciliation and reference tests, not legacy shadowing

The originating plan's step 5 proposed shadow reads comparing old weekly results with rollup-derived
results. **That is impossible here: the weekly table is empty and the legacy path has never
succeeded** **[PF]**. The legacy Python transform is **not** validation baseline and **not**
operational rollback support.

**[REQ]** Validate through three mechanisms:

1. **Exact raw-SQL reconciliation.** Rollup sums must match direct aggregation of raw rows per
   source, warehouse, client, and week at the fixed cutoff. Dispatch and loss totals are asserted
   independently. Discrepancies must never exceed dispatch orders on any reported dimension.
   Reconciliation is a first-class, re-runnable job, not a one-off script.
2. **Bounded reference tests** with deterministic fixtures and hand-computed expected outputs,
   covering: UTC bucket boundaries; ISO-week boundaries including year rollover; dispatch/loss
   separation; zero-activity dimensions in the dense grid; discrepancy-rate derivation including the
   zero-denominator case; fixed-cutoff exclusion of rows arriving mid-run; trailing-window
   recomputation of a late arrival; and idempotent re-run producing identical rows.
3. **Migration tests** verifying upgrade and downgrade, indexes, uniqueness, and compatibility with
   the prior application image.

If reconciliation fails, record the exact mismatches, retain the existing publication path, and do
not activate rollup-backed reads.

### 5.5 Warehouse vocabulary (D-8)

`LA` and `ZGZ` become the **canonical internal codes** used in rollup storage, computation, and
internal contracts. The existing public reporting values `los_angeles` and `zaragoza` are
**preserved by boundary mapping** in the reporting response layer. No published value changes in
this engagement. If a consumer later needs canonical codes, add them as an additive field or a
versioned endpoint — never by silently changing existing values.

### 5.6 Statement timeouts

The Central API default `database_statement_timeout_ms` of 15,000 stays. The rollup job runs its
aggregation and upsert statements under an explicitly raised session statement timeout of
**60,000 ms**, set on the reporting connection only. **[REQ]** No single aggregation statement may
exceed **30 s** at the §7.3 performance-test volume.

### 5.7 Phase 6.2 acceptance

1. Reconciliation is **exact** across every source, warehouse, client, and week at the fixed cutoff.
2. All reference tests and migration tests pass.
3. Rollup computation meets the §7.3 budgets at current volume and at the synthetic projection.
4. The feature flag defaults to off; served responses are byte-identical to before the phase.
5. `pipeline_run_attempts` rows now carry `source_cutoff_at`, `rows_scanned`, and
   `rollup_rows_written`.

---

## 6. Phase 6.3 — Reconciled cutover with safe degradation

Rollups become authoritative. Prefect still executes claimed runs.

### 6.1 Cutover

1. Populate the existing weekly table from verified hourly rollups.
2. Mark the rollup version active in `rollup_state` **only after** reconciliation passes.
3. Reporting reads become: published weekly rows for complete historical weeks; hourly rollups for
   the current incomplete week; sums of weekly rows for longer historical periods.
4. Retire the raw-row Python transformation and the R2 transformation-cache path from the
   computation path.

### 6.2 Rollback semantics **[REQ]**

Reverting **never** reactivates the legacy transform. Reverting means one of:

- **Serve the last verified published snapshot, explicitly labelled stale**, with its
  `source_cutoff_at` and publication time visible in the response and in the UI; or
- **Disable reporting computation by flag**, with the Back Office rendering a truthful degraded
  state and reporting endpoints returning a safe `503` with a stable error code.

Rollup tables and attempt history remain intact in both paths. No destructive downgrade.

### 6.3 Transient-failure classification (D-2) **[REQ]**

Any inner retry inside the reporting execution path applies **only** to explicitly classified
transient connectivity failures. Define the classification as an explicit allowlist:

**Retryable (transient connectivity only):** connection refused or reset; connection closed
unexpectedly; connect timeout; pooler or server temporarily unavailable; DNS resolution failure.

**Never retried inside the executor:** statement timeout; lock timeout; integrity, constraint, or
check violations; permission and grant errors; programming, syntax, and type errors; serialization
failures requiring transaction-level handling; and any unclassified exception.

Unclassified and non-transient failures propagate immediately to the queue's existing retry and
backoff machinery with their originating `error_code`, and are recorded in `pipeline_run_attempts`
with the true exception class. **A blanket `except Exception` retry is prohibited.**

### 6.4 Reporting status contract

Extend reporting status with: state; last successful cutoff; publication time; current stage and
progress; latest safe error code and attempt count; and whether displayed results are current or
stale. Preserve existing report-request and weekly-report response compatibility. Manual refresh
queues an idempotent request and performs no raw computation inside an HTTP request. When the
reporting control plane is unavailable, reporting endpoints return a safe, truthful `503` while
unrelated Back Office routes remain fully functional.

`uis/backoffice/components/reporting/BusinessReportingView.tsx` renders stale and degraded states
and the last successfully published data rather than failing.

### 6.5 Phase 6.3 acceptance

1. **First successful publication in production** — the primary success criterion of this
   engagement.
2. Reconciliation re-verified against live data after cutover.
3. Report reads meet the §7.3 budget.
4. **Both** rollback paths exercised and verified.
5. Reporting endpoints return a safe `503` under a forced control-plane outage while unrelated Back
   Office routes return zero 5xx and zero 404.
6. Seven-day production observation with alerts for: no successful rollup within one cadence period
   plus grace; a stage exceeding its deadline; repeated retries; reconciliation failure; database
   size approaching the soft threshold; and Back Office route failure independent of reporting
   status.

---

## 7. Phase 6.4 — Measured re-budget and Prefect executor replacement

Begins only after Phase 6.3 has been stable through its seven-day observation window.

### 7.1 Measurement — three separate studies (D-6)

| Study | Window | Conditions |
|---|---|---|
| **Steady state** | **48 uninterrupted hours** | No deployments, no limit changes, no restarts. Must span at least two scheduled reporting cycles, one daily prune (02:15 America/Chicago), and four size-guard ticks |
| **Deployment** | Per deployment, measured on its own | Image pull, startup chain, peak transient CPU and RSS, attach duration. **Never averaged into steady state** |
| **Post-change comparison** | **48 hours after each change** | Same protocol as steady state, compared against the steady-state baseline |

Per container: mean and **peak** CPU, mean and **peak** RSS, peak-to-limit ratio, OOM-kill count,
restart count. Host: mean and peak CPU, RSS, swap, load, free disk, Docker events, container exit
codes. Sampling interval ≤ 60 s, non-invasive. Raw series are retained as deployment evidence, not
only summaries.

**Decision rule [REQ].** Docker limits are **ceilings, not consumption**. Lower a limit only where
measured peak ≤ 60% of the proposed new ceiling across the full steady-state window with zero OOM
kills. Raise a limit where measured peak ≥ 80% of the current ceiling. Otherwise leave it unchanged.
One change at a time, each followed by a post-change comparison window. The originating plan's
"≥ 2 GiB sustained RAM headroom" gate is redefined as **measured free host memory at peak**, not
ceiling arithmetic.

Context for interpretation, not a mandate: declared ceilings currently total **4.15 vCPU (208% of
2)** and **6,272 MiB of 8 GB**, before Coolify, Traefik, dockerd, and the OS **[RF]**. That is a
commitment risk, not evidence that any container is oversized.

### 7.2 Prefect executor replacement — a swap, not a redesign

**Explicitly unchanged and out of scope** (per §2.3): scheduling, manual and CLI requests, claiming,
leases and renewal, retry and backoff, terminal transitions, stale-lease recovery, advisory-lock
single-publisher enforcement, and the worker heartbeat.

**The change [REQ]:** implement a direct SQL executor satisfying the existing `RunExecutor`
contract — `(engine, claim, abort) -> RunMetrics` — inside the existing reporting worker container,
and swap it for `flows.prefect_executor`.

Retain: stage recording under claim-token CAS; abort-event checks; `verify_claim_for_publication`
inside the publishing transaction; and the `PipelineStageError` code taxonomy.

Two details that must be handled explicitly:

1. **Stage-recording enforcement** currently keys off the presence of a Prefect run context
   (`enforce=flow_run_id is not None`) **[RF]**. It must become unconditional in production once the
   Prefect context is gone.
2. **Extract-level retries** currently come from Prefect task decorators (3 attempts, 10 s delay)
   **[RF]**. Reimplement them explicitly in the SQL executor under the §6.3 transient-connectivity
   classification. Do not delegate them to queue-level retry, which carries a 60–480 s backoff and
   would consume a full attempt for a transient blip.

**Verification before removal [REQ]:**

- The direct executor produces **identical rollups** to the Prefect path on the same fixed cutoff.
- Scheduled execution, manual trigger, retry and backoff, lease renewal, worker-restart recovery,
  and stale-lease recovery are each exercised in production.
- A **7-day clean-run period** elapses (D-1).

**Removal [REQ]:** only then remove `prefect-server`, `prefect-postgres`,
`prefect-postgres-bootstrap`, `prefect-db-backup`, `prefect-postgres-guard`,
`prefect-version-guard`, and the Prefect runtime dependency. The reporting worker **remains its own
container and its own failure domain**. `pipeline_runs.prefect_flow_run_id` is retained as a
nullable historical column and is **not** dropped.

**Preservation [REQ]:** file a `docs/archive/` retirement note recording what the dedicated-Prefect
architecture delivered, why it was retired, the acceptance evidence, and where the history lives.
The completed work is preserved through that note and git history, per `AGENTS.md` "Preserving
Milestone Work" — not by keeping unused code on disk.

### 7.3 Performance budgets **[REQ]**

Tested at not less than twice the projected six-month volume at the post-change 15 s feed interval.

| Budget | Threshold |
|---|---|
| Regular 12-hour rollup run | ≤ 60 s |
| Full-history rollup (one-shot) | ≤ 60 s |
| Report read | ≤ 2 s |
| Any single aggregation statement | ≤ 30 s |
| Reporting worker RSS | ≤ 80% of its limit |

### 7.4 Phase 6.4 acceptance

1. Post-change 48-hour comparison shows measured host headroom meeting the redefined gate, with zero
   OOM kills and no unexplained restarts.
2. All dispatch, retry, lease, and recovery paths verified in production without Prefect.
3. Identical-output verification recorded.
4. Retirement note filed in `docs/archive/`.
5. Database growth trajectory documented against the reset threshold at the 15 s feed interval,
   **with no ledger rows deleted**.

---

## 8. Contracts frozen by this specification

### 8.1 Health and release

Three signals, exactly as in §4.1.c. **Only core readiness excluding reporting may trigger
deployment rollback.** Reporting verification is reported and never rolls back. Back Office
liveness verifies the Next.js process only.

### 8.2 Database access

Supabase business data is owned by Central API. Direct database connections are limited to Central
API and the **explicitly approved background workers** — `operations-feed`, the reporting worker,
and `maintenance-worker` — each using the least-privileged runtime role with an explicitly capped
connection pool, within the observed 60-connection ceiling (24 currently in use, 10 held by
`trackflow_runtime`) **[PF]**.

**No future UI, agent, MCP, or workflow service may connect to Supabase directly.** Those consume
Central API over HTTP. Adding a direct connector requires an explicit, approved decision — never a
default. Every pool must declare a maximum size, and the sum of declared maxima must be documented
against the 60-connection ceiling.

### 8.3 Business-data classification (forward-looking, stated once) (D-9)

Agent conversations, approved agent memory, memory-proposal decisions, MCP authorization and
invocation records, and RFP approvals are **business data** — auditable, retained, backed up, and
privacy-governed. The disposable-data waiver covering the synthetic inventory ledger **does not
extend to them**. Physical placement, backup mechanism, and retention windows are deferred to
Engagement 7/8 planning. **No implementation in this engagement.**

### 8.4 Immutable ledger

`stock_entries` and `stock_exits` are immutable and are not deleted, archived, or compacted in this
engagement. Any future scheme that removes movement rows must first prove, in its own approved
design, that computed stock and audit correctness are preserved — because stock is computed from the
full movement history, and removing movements silently changes computed stock.

### 8.5 Reporting API

`/reporting/*` response shapes and the six queue states (`idle`, `processing`, `queued`, `retrying`,
`stuck`, `unavailable`) are preserved. Public warehouse values remain `los_angeles` and `zaragoza`
(§5.5). Additive fields are permitted; changes to existing field semantics are not.

---

## 9. Deliberate departures from the July 23 originating plan

| Plan item | Departure | Reason |
|---|---|---|
| §4 "Keep Prefect as a thin, isolated coordinator", listed as a fixed assumption | Phased retirement in 6.4 after verification | Prefect executes only already-claimed runs; PostgreSQL and the worker already own everything else (§2.3) |
| §4 Isolated reporting Coolify resource with its own Prefect server, Prefect PostgreSQL, and worker | Not adopted | Superseded by executor replacement; no new topology |
| §4 "≥ 2 GiB sustained RAM headroom" precondition | Redefined as measured free host memory at peak (§7.1) | Ceiling arithmetic already exceeds capacity, so the gate as written blocks its own plan |
| §3 `reporting.dirty_rollup_buckets` | Deferred with a stated trigger condition (§5.3.8) | Sources are append-only; the trailing 72-hour window covers every current path |
| §4 Backfill with 100,000-row daily ceiling, 6-hour subdivision, resumable cursor | Not adopted | Full-history rollup measures ~410 ms and ~5,100 rows (§1.2); only 8 rows predate 2026-07-13 |
| §5 Rollout step 5, shadow reads against old weekly results | Replaced by raw-SQL reconciliation plus bounded reference tests (§5.4) | The weekly table is empty; there is nothing to shadow |
| §5 Rollout step 10, retain old reporting code as rollback | Not adopted | The legacy transform has never succeeded; rollback is the stale-snapshot or safe-disable path (§6.2) |
| §2 Health-check separation | Extended to three signals, with the release gate on core readiness and reporting verification made non-rollback (§4.1.c) | The plan did not address the Dockerfile `HEALTHCHECK` or the deployment poll, so nothing would have changed |
| §2 Bounded Docker log rotation and notifications | Extended with host-persisted logs and durable events, governed by rotation, retention, disk limits, permissions, and content safety (§4.1.b) | `json-file` logs are destroyed when a container is replaced |
| Not addressed by the plan | Destructive size-guard protection moved into Phase 6.1 (§4.1.g) | The guard truncates the ledger unattended with a checkpoint that currently always fails |
| Not addressed by the plan | Second execution path removed from `maintenance-worker` (§4.1.e) | Two processes can currently execute reporting runs |
| Not addressed by the plan | Warehouse vocabulary canonicalized internally, public values preserved (§5.5) | Two vocabularies exist across one public API |
| §2 Stage deadlines 300 / 180 / 900 s | Replaced with the coherent set in §4.1.d | Must satisfy stage deadline < lease < watchdog |

---

## 10. Approved owner decisions

| ID | Decision | Resolution |
|---|---|---|
| OD-1 | Prefect retirement gate | Minimum verification set **plus a 7-day clean run** |
| OD-2 | Extract-retry behaviour after the swap | Explicit bounded retry in the SQL executor, transient connectivity only |
| OD-3 | Rollup cadence | Hourly buckets, execution every 12 h, trailing 72 h recomputation, manual refresh available |
| OD-4 | Database growth | Feed interval **fixed at 15 s**, plus soft-threshold slow/pause and owner-approved reset |
| OD-5 | Diagnostic evidence | Host-persisted log path **plus** durable critical-path events |
| OD-6 | Measurement | Three studies: 48 h steady state, separate deployment measurement, 48 h post-change comparison |
| OD-7 | Deployment gate | Core readiness excluding reporting; reporting verification separate and non-rollback |
| OD-8 | Warehouse vocabulary | `LA`/`ZGZ` canonical internally; public values preserved by boundary mapping |
| OD-9 | Backup posture for business-class agent/workflow data | Principle stated now (§8.3); mechanism deferred to Engagement 7/8 |
| OD-10 | Sales-forecasting dataset | **Resolved:** generate `data/raw/trackflow_sales.csv` to the documented specification with a fixed seed and an explicit provenance note recording the deviation from "do not generate or simulate it". Delivered under the separate 6.5 specification, in parallel. Not blocking 6.1–6.4 |

---

## 11. Files in scope

Indicative, not exhaustive. The implementation plan should confirm against the repository.

**Health and deployment:** `docker/backoffice.Dockerfile`; `uis/backoffice/app/api/health/route.ts`;
`services/central-api/central_api/health.py`; `services/central-api/central_api/main.py`;
`.github/workflows/deploy-production.yml`.

**Reporting domain:** `services/central-api/central_api/domains/reporting/{models,repository,schemas,service,router,status}.py`;
`services/central-api/migrations/versions/`.

**Pipeline:** `data/pipelines/business_performance/{queue,runner,worker,dispatcher,locks,flows,cache,startup_guard,prefect_version}.py`;
`data/process/business_performance/{weekly_kpis,vocabulary}.py`.

**Workers and guards:** `services/central-api/scripts/{db_size_guard,maintenance_worker,operations_feed,prune_*}.py`;
`services/central-api/central_api/core/config.py`; `services/central-api/central_api/domains/operations/`.

**Compose:** `compose.yaml`, `compose.coolify.yaml` (Phase 6.4 removals; 6.1 feed interval and log
path).

**UI:** `uis/backoffice/components/reporting/BusinessReportingView.tsx`;
`uis/backoffice/lib/reporting/`.

**Docs, per phase:** `README.md` roadmap row and "What's Been Built";
`docs/briefs/06-data-pipelines-telemetry.md` Status; `docs/briefs/README.md`; `CLAUDE.md`;
`memory-bank/progress.md`; `docs/runbooks/business-performance-pipeline.md`,
`backend-coolify-deployment.md`, `operations-feed.md`, `telemetry-inventory.md`;
`docs/archive/` retirement note (Phase 6.4).

---

## 12. Review gates

Each phase ends here. Do not begin the next phase before written owner approval.

1. Ruff, mypy, package build, and pytest with coverage pass for Central API and Identity; Back
   Office type-check, lint, build, and tests pass.
2. The phase's acceptance criteria are met, with evidence attached — measurements, test output,
   reconciliation results, or verification records as applicable.
3. Engagement-tracking documentation updated per `AGENTS.md` §3.
4. No protected path modified outside scope; no unrelated worktree change disturbed.
5. Commit message names the engagement and the phase.
6. **Stop and request review.**
