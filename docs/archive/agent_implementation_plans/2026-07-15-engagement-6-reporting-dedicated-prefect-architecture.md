# Engagement 6 — Reporting Pipeline Production Fix: Dedicated Prefect Architecture (rev 3)

Planning-only review of the business-performance pipeline production incident. No files were
modified. All code facts verified against `origin/main` (a072a86, PR #17 merged); the local
checkout is on `main`, 5 commits behind — **pull before implementing**.

Rev 2 incorporated reviewer corrections: documented Prefect DB setting name + SQLite-fallback
guard, continuous lease renewal, decoupled/pinned Prefect server image, explicit restart-recovery
semantics, split `ORCHESTRATION_FAILED`/`INTERNAL_FAILED` taxonomy, Prefect-database durability
regimen, smaller per-phase blast radius, and expanded watchdog test obligations.
Rev 3 closes the final four gaps: readiness never accepts a renewed lease as progress (stage
deadlines + orchestrator health are required signals); explicit PostgreSQL↔Prefect run
correlation (`prefect_flow_run_id` + deterministic run names + startup orphan reconciliation);
an explicit runner lifecycle refactor so claim-scoped renewal is implementable; and completed
Prefect operations (digest-pinned server image, deploy-time client/server version check,
approval-gated upgrade procedure, a dedicated `pg_dump`-capable backup service with
least-privilege R2 credentials).

## Context

The hardened deployment succeeded (migrations through `20260715_0009`, immutable SHA, readiness,
smoke tests), but reports do not complete. The queue shows one scheduled run stuck `running` with
a stale execution heartbeat, newer manual runs stuck `requested`, and older runs `retryable` with
`LOAD_FAILED` — while the worker heartbeat stays healthy and readiness stays green.

Owner decision (July 15, 2026, this session): move to a **production-grade dedicated Prefect
deployment** — internal Prefect server backed by a dedicated PostgreSQL database, R2-backed
persisted results, version-pinned, with retention, readiness, and resource isolation — while the
PostgreSQL queue (`reporting.pipeline_runs`) **remains the sole authoritative execution state**,
and the existing worker keeps claiming from it and executes flows **in-process** against the
dedicated server (no work-pool dispatch; confirmed in Q&A). This supersedes PIPELINE_DESIGN §9.6's
"no permanent Prefect server" boundary — the design doc must be amended (Phase 1).

---

## 1. Root cause

**Confirmed facts (code + logs):**

- `data/pyproject.toml` / `data/uv.lock`: **Prefect 3.7.8**, used as a library. No
  `PREFECT_API_URL` is set anywhere in `compose.coolify.yaml`.
- With no API URL, Prefect 3 runs in **ephemeral mode**: each flow execution talks to a
  `SubprocessASGIServer` — a uvicorn Prefect API subprocess with SQLite state under
  `PREFECT_HOME=/tmp/trackflow/prefect` (tmpfs). Official docs treat this as a convenience mode;
  production self-hosting guidance is a dedicated `prefect server start` with PostgreSQL
  ([server concepts](https://docs.prefect.io/v3/concepts/server),
  [ephemeral settings](https://reference.prefect.io/prefect/settings/models/server/ephemeral/)).
- `worker.py` is a **long-running single process**: serial poll loop calls `prefect_executor`
  per claim; heartbeat (10 s) and dispatcher (60 s) run on separate threads. The worker
  heartbeat therefore proves only that the *threads* are alive, not that the poll loop can
  process work.
- Logs show temporary servers churning across loopback ports (8202, 8247, 8429),
  `address already in use`, `POST /api/flow_runs/ 422`, `PrefectHTTPStatusError`. Extraction
  tasks complete before orchestration fails.
- **Error-taxonomy defect (confirmed in code):** in `flows.py:_stage_failure`, any non-SQLAlchemy
  exception outside extract — including Prefect orchestration errors — maps to `LOAD_FAILED`;
  `runner.py`'s generic handler does the same. The `LOAD_FAILED` rows are misclassified
  orchestration failures, not load failures.
- **Lease-renewal gap (confirmed in code):** `renew_pipeline_lease` runs only *between* the
  extract, transform, and load subflows. Any single stage exceeding the 600 s lease loses it even
  while healthy, and a hung stage renews nothing.
- Memory: ~605 MiB of the 768 MiB limit — worker Python + Prefect engine + uvicorn subprocess(es)
  + SQLite. Raising memory would not fix port collisions or server lifecycle.

**Inferences (plausible, need log confirmation in Phase 0):**

- The stuck-`running` run: a Prefect client call inside `prefect_executor` hung (retrying against
  a dead/half-started ephemeral server), blocking the serial poll loop. Execution heartbeats
  stopped; the worker-heartbeat thread kept updating. Newer requests stayed `requested` because
  the only claimer was blocked. The dispatcher thread's `recover_stale_runs` should transition
  the row to `retryable` ~10 min after lease expiry — either observation preceded expiry, or the
  sweep is also impaired; confirm from logs.
- The 422s are most plausibly stale/corrupted subprocess-server SQLite state or a partially
  initialized server within the long-lived process (client and server versions are identical in
  one image, ruling out version skew).

**Root-cause statement:** a persistent production worker repeatedly drives Prefect 3.7.8 through
its ephemeral subprocess-server mode — a lifecycle designed for short-lived dev/CLI use — inside a
memory-capped, read-only container. Orchestration itself becomes the failure point after
extraction succeeds; those failures are misclassified as `LOAD_FAILED`, consume queue attempts,
and a hung orchestration call wedges the serial claim loop while heartbeat/readiness keep
reporting healthy.

---

## 2. Option comparison (evaluated; decision recorded)

| Option | Reliability | Memory | Ops complexity | Durability/rollback | Verdict |
|---|---|---|---|---|---|
| 1. Dedicated internal Prefect server (+ dedicated Postgres) | High — documented production lifecycle; one stable API; no port churn | +~700 MiB (server ~512 + Postgres ~256), −~300 in worker | Two new services, retention + backups to manage | PG queue untouched; image-only rollback safe (server image decoupled, §4) | **Chosen (owner decision)** |
| 2. Direct execution, no runtime Prefect (flows stay for CLI/milestone) | High — removes the failing layer entirely | Lowest (worker ~150–250 MiB) | Lowest | Unchanged | Was my recommendation; declined |
| 3. Prefect Cloud / external service | High | Low local | External SaaS, credentials, egress from private worker | State off-box | Rejected — violates approved boundary |
| 4a. Dedicated server on SQLite/tmpfs | Medium — docs: SQLite for lightweight single-server; state lost per restart | +~512 MiB | Lower than 1 | Same | Rejected by owner ("dedicated PostgreSQL") |
| 4b. Prefect state in TrackFlow Supabase | — | — | — | Consumes the 450 MB Free budget; `db_size_guard` doesn't manage it; needs `pg_trgm` | **Rejected — must not share Supabase** |
| 5. Memory bump only | No — lifecycle/port collisions persist | +N | None | — | Rejected as sole fix |
| 6. Work pools/workers as dispatch | — | +1 container | Dual queue authority vs `reporting.pipeline_runs` | Conflicts with stated constraint | Scoped out per Q&A; PG queue + in-process flows chosen |

**Why the chosen architecture fits TrackFlow:** it keeps every durable guarantee where it already
lives (PostgreSQL queue: leases, CAS tokens, advisory lock, single-active index, retries,
idempotent load) and gives Prefect the one thing it was missing — a stable, supported API
lifecycle — without letting Prefect become a second authority.

---

## 3. Target architecture

- **`prefect-postgres`** (new Compose service): pinned `postgres:16.x` digest, internal-only,
  named volume `prefect-db`, own credentials (`PREFECT_DB_PASSWORD` secret), init script enabling
  `pg_trgm`, healthcheck `pg_isready`, limit ~256 MiB.
- **`prefect-server`** (new Compose service): runs from a **separately pinned Prefect image**
  (`${PREFECT_SERVER_IMAGE}` = `prefecthq/prefect:3.7.8-python3.11` **pinned by digest
  (`@sha256:...`), not tag alone**) —
  **deliberately decoupled from `TRACKFLOW_IMAGE_TAG`** so application image rollback never
  downgrades the server binary underneath an upgraded Prefect schema. Prefect documents that
  older clients generally work against newer servers while newer clients can 422 against older
  servers, so the server version must always be ≥ the client version shipped in the app image;
  Prefect upgrades are their own change (upgrade server first, then app image).
  Command `prefect server start --host 0.0.0.0 --port 4200`; database via the **documented
  setting `PREFECT_API_DATABASE_CONNECTION_URL=postgresql+asyncpg://prefect:...@prefect-postgres:5432/prefect`**
  (verify against 3.7.8 at implementation; if a `PREFECT_SERVER_DATABASE_*` alias also exists,
  set the documented name and rely on the fallback guard below, not on guesses).
  **SQLite-fallback guard (required):** deployment verification must assert the server is
  actually on Postgres — after startup, check that Prefect's tables exist in `prefect-postgres`
  (`psql`/`pg_isready` + table probe) and fail the deploy if not; a misspelled setting silently
  reverts to SQLite, which is exactly the failure mode being removed.
  Telemetry/analytics off (existing env block), `PREFECT_HOME=/tmp/prefect`, read-only + tmpfs,
  internal-only (never exposed via the Coolify proxy), healthcheck `GET /api/health`,
  limit ~512 MiB initially (re-budgeted in Phase 4). Document the Prefect **database migration
  procedure** (server auto-migrate on start vs explicit `prefect server database upgrade`) as
  part of the runbook, pinned to the chosen behavior.
- **`reporting-worker` / `maintenance-worker`**: unchanged claim loop and schedule; add
  `PREFECT_API_URL=http://prefect-server:4200/api` and a bounded `PREFECT_API_REQUEST_TIMEOUT`.
  Both need it (`db_size_guard.run_reporting_checkpoint` also calls `prefect_executor`). Flows
  execute in-process; orchestration state lives on the server.
- **Restart-recovery semantics (explicit):** the dedicated server records task/flow *state*, but
  completed work is reusable across a worker restart **only when results are persisted**.
  Current tasks are `persist_result=False`. Therefore: with R2 absent, a retried run **re-runs
  completed tasks** (correct today — extraction is idempotent, load is transactional and
  idempotent); with R2 configured and result persistence enabled (Phase 3), completed task
  results can be reused across retries; side-effecting tasks (load) must remain idempotent
  regardless of persistence — persistence is an optimization, never a correctness mechanism.
- **PG queue stays authoritative:** claim/lease/CAS/advisory-lock/idempotent-load code paths in
  `queue.py`, `runner.py`, `locks.py` keep their semantics (lease renewal is strengthened, §4).

---

## 4. Exact changes by file

### Compose (`compose.coolify.yaml`, mirror dev equivalents in `compose.yaml`)
- Add `prefect-postgres` + `prefect-server` per §3 (inherit `x-runtime`; no public exposure;
  `prefect-server` image from `${PREFECT_SERVER_IMAGE:?required}`, not `TRACKFLOW_IMAGE_TAG`).
- `reporting-worker`: add `PREFECT_API_URL`, `PREFECT_API_REQUEST_TIMEOUT` (e.g. `30`),
  `depends_on: prefect-server: service_healthy`. `maintenance-worker`: same env, **no** hard
  dependency (pruning must run even if Prefect is down; its checkpoint path degrades like any
  orchestration failure).
- Add `prefect-db-backup` service (§Prefect database durability) with `PREFECT_BACKUP_R2_*` and
  read-only Prefect DB credentials only.
- Add volume `prefect-db`.

### Pipeline code (`data/pipelines/business_performance/`)
- **Runner refactor (required — makes continuous renewal implementable):** today `worker.py`
  calls `run_once()`, which claims internally, so the worker never holds the claim early enough
  to start a claim-scoped renewal thread. Split `runner.py` into an explicit lifecycle the worker
  drives:
  1. `claim_next(engine)` (existing, unchanged semantics),
  2. `execute_claim_with_renewal(engine, executor, claim)` — starts the renewal thread, takes the
     advisory lock, runs the executor, stops the thread,
  3. `finalize_claim(engine, claim, outcome)` — the existing token-CAS success/retryable/failed
     transitions.
  `run_once()` remains as a thin composition of the three (CLI and `db_size_guard` checkpoint
  keep working unchanged); all existing state-machine semantics and tests are preserved.
- **Continuous lease renewal (required):** the claim-scoped renewal thread renews via the
  existing CAS `heartbeat()` every 60 s (`REPORTING_HEARTBEAT_SECONDS`) **independent of stage
  boundaries**, so a long single task can never outlive the 600 s lease while healthy. On CAS
  failure (lease lost) it sets an abort Event; stage boundaries and
  `verify_claim_for_publication` (already inside the load transaction) enforce the abort — a
  zombie still cannot publish. The between-stage `renew_pipeline_lease` task becomes redundant
  and is removed. A renewed lease proves **ownership only, never progress** — it is deliberately
  excluded from readiness (§ Readiness).
- **PostgreSQL↔Prefect run correlation (required):** `reporting.pipeline_runs` gains a nullable
  `prefect_flow_run_id uuid` (set — token-CAS-guarded — as soon as the flow run exists, cleared
  semantics: kept for history on terminal rows), and the flow run is created with a
  deterministic name `business-performance-{run_id}-attempt-{attempt}`. Recovery after a
  watchdog exit or crash uses the stored ID (name as fallback search) to find and force the
  orphaned Prefect run to a terminal state (`Crashed`/cancelled) during worker startup
  reconciliation. Without this mapping orphan cleanup would be guesswork.
- **Stage progress for readiness:** the executor records `current_stage`
  (`extract|transform|load`) and `stage_started_at` on the run row (token-CAS-guarded, small
  separate transactions at stage boundaries). Stage deadlines are config:
  `REPORTING_STAGE_TIMEOUT_EXTRACT/TRANSFORM/LOAD_SECONDS` (defaults 300/300/300, tuned from
  Phase 0 duration evidence). These drive the readiness/`stuck` rules below.
- **Error taxonomy split:** `ORCHESTRATION_FAILED` (retryable) **only** for known Prefect
  API/client failures (`PrefectHTTPStatusError`, Prefect client connection/timeout types);
  `INTERNAL_FAILED` (retryable) for unknown exceptions (application code, serialization, cache
  handling) — both keep stage + exception type in safe fixed-token logs; nothing sensitive.
  `LOAD_FAILED` returns to meaning actual load-stage failures. Extend `ErrorCode` +
  `_SAFE_ERROR_SUMMARIES` in `queue.py`, mapping in `flows.py:_stage_failure` and `runner.py`.
- `worker.py`:
  - Main poll loop stamps **`last_progress_at`** (new column, §migration) each iteration via the
    heartbeat upsert — proves the loop can process work, not just that threads live.
  - **Run watchdog (last-resort backstop):** monitor thread; if a single `run_once` exceeds
    `REPORTING_RUN_TIMEOUT_SECONDS` (default 1800), log a fixed-token line, flush handlers, and
    `os._exit(1)`; `restart: on-failure` recovers; lease sweep reclaims the run. This is
    deliberately violent and acceptable **only because** transactions, claim tokens, and
    idempotent publication protect the data — the test matrix in §8 must prove that.
  - Pre-claim Prefect health probe: if `GET {PREFECT_API_URL}/health` fails, skip claiming
    (leave rows `requested`), record `orchestrator_healthy=false` in the heartbeat row.
- `queue.py`: `record_worker_heartbeat` gains optional `last_progress_at` /
  `orchestrator_healthy`; engine gains bounded connect/statement timeouts from env (mirror
  central-api's `DATABASE_CONNECT_TIMEOUT_SECONDS` / statement-timeout pattern).
- `cache.py` boto3 client: explicit `connect_timeout`/`read_timeout` + `retries={max_attempts:2}`
  so R2 can never hang a run.

### Migration (`services/central-api/migrations/versions/20260716_0010_...`)
Additive only (image-only rollback stays safe):
- `reporting.worker_heartbeats`: add `last_progress_at timestamptz NULL`,
  `orchestrator_healthy boolean NULL`.
- `reporting.pipeline_runs`: add `prefect_flow_run_id uuid NULL`, `current_stage text NULL`
  (CHECK in extract/transform/load), `stage_started_at timestamptz NULL`.
- Recreate `ck_pipeline_runs_error_code` to include `'ORCHESTRATION_FAILED'` and
  `'INTERNAL_FAILED'`.
- **Compatibility check before merge:** confirm the central-api reporting response schemas type
  `error_code` as `str` (not a Literal) so an old image can serialize new codes; widen if not.

### Readiness (`services/central-api/central_api/health.py`)
Replace `_check_reporting_worker`'s heartbeat-only rule with "can actually process work".
**A renewed lease is deliberately not evidence of progress** — the renewal thread keeps renewing
even while a Prefect call hangs, which would reproduce today's misleading green readiness. Ready
iff **all** of:
- worker heartbeat fresh (30 s), **and**
- `orchestrator_healthy = true`, **and**
- when no run is `running`: `last_progress_at` fresh within `REPORTING_PROGRESS_STALE_SECONDS`
  (default 120), **and**
- when a run is `running`: `stage_started_at` within that stage's deadline
  (`REPORTING_STAGE_TIMEOUT_*`, §Pipeline code).

A `running` row whose current stage exceeds its deadline makes readiness fail (fixed-token id
`reporting_stage_stuck`) and drives the API `queue_state` to `stuck` — **regardless of whether
other work is queued**. Other fixed-token ids: `reporting_worker`, `reporting_orchestrator`,
`reporting_progress`. Central API never calls the Prefect server — worker-reported DB state only.

### Reporting API (`services/central-api/central_api/domains/reporting/`)
`ReportingWorkerHealth` gains `last_progress_at`, `orchestrator_healthy`; add server-derived
`queue_state: "idle"|"processing"|"queued"|"retrying"|"stuck"|"unavailable"`
(`stuck` = a `running` row's current stage exceeds its deadline, or no run active with heartbeat
healthy but poll progress stale — in both cases regardless of queued work; `unavailable` =
heartbeat stale or `orchestrator_healthy=false`; `retrying` = latest run `retryable` with
`next_attempt_at`). Same rules as readiness — one derivation, shared.

### Back Office (`uis/backoffice/components/reporting/BusinessReportingView.tsx`)
Render `queue_state` explicitly (today `retryable` displays as "queued" and "stuck" is
undetectable): queued ("waiting behind the current run"), processing, retrying ("attempt N of 5,
next try at …"), unavailable ("reporting worker/orchestrator is not responding; queued work will
wait"), stuck ("worker is running but not making progress — see runbook"), plus existing
stale->26 h and failed(`error_code`) notices. Types in `lib/reporting/types.ts`; no new deps.

### Prefect database durability, retention, and bounding
Business work never depends on Prefect state (PG queue is authoritative), but losing it loses
task-level recovery and history, so treat it as genuinely durable:
- **Dedicated backup service (not the maintenance worker):** a small `prefect-db-backup` Compose
  service built on a **pinned `postgres:16` image** (which actually ships `pg_dump` — the
  central-api image may not, and the maintenance worker must not accumulate Prefect DB
  credentials plus PostgreSQL client tools). It runs a simple loop: daily `pg_dump -Fc` of
  `prefect-db` uploaded to the private R2 bucket (via a pinned CLI or a ~50-line Python/boto3
  script baked into a tiny derived image) under a dedicated `prefect-backups/` prefix, retained
  7 days. **Least-privilege R2 credentials:** a separate R2 token scoped to that prefix/bucket
  (`PREFECT_BACKUP_R2_*` env vars), never the reporting cache credentials. Only when R2 is
  configured; absent R2, it logs a fixed-token "backups disabled" notice — never blocks
  reporting. It holds read-only Prefect DB credentials and nothing TrackFlow.
- **Restore verification:** production acceptance includes one restore drill into a scratch
  container (`pg_restore` + Prefect table probe).
- **Volume checks:** ownership/permission validation at deploy verification; disk-size sampling
  by the backup service with a fixed-token warning threshold.
- **Retention:** daily deletion of Prefect flow runs older than `PREFECT_RUN_RETENTION_DAYS`
  (default 30) via the Prefect REST API from the maintenance worker (API-only — no DB
  credentials needed; prefer a server-side retention setting if 3.7.8 ships one — verify); plus
  routine autovacuum defaults.
- **Migration/upgrade procedure (approval-gated, separate from app releases):** documented in
  the runbook — Prefect server/database upgrades are their own change with owner approval, never
  a side effect of an application deploy: bump the digest-pinned `PREFECT_SERVER_IMAGE`, take a
  backup, apply the Prefect schema migration (pinned auto-migrate vs explicit
  `prefect server database upgrade` — verify 3.7.8 behavior and pin it), verify `/api/health`,
  then (and only then) any app-image Prefect client bump. Always server ≥ client.

### Design doc & workflow
- `data/pipelines/PIPELINE_DESIGN.md` §5/§9.6: record the owner-approved amendment.
- `.github/workflows/deploy-production.yml`: add the SQLite-fallback guard and Prefect-server
  health probe to release verification, plus a **client/server compatibility check** before
  deploy: read the app image's locked `prefect` version (from the image or `data/uv.lock` at the
  deployed SHA) and the running server's version (`GET /api/version` or image digest mapping);
  fail if client > server. Deployment summary lists the pinned `PREFECT_SERVER_IMAGE`.
  **Rollback path:** automatic/manual rollback changes only `TRACKFLOW_IMAGE_TAG`; the Prefect
  server image and schema are never rolled back with it (upgrades follow the separate
  approval-gated procedure above).

---

## 5. Resource budgeting (measured, not arbitrary)

1. **VPS evidence (captured July 15, 2026):** 7.8 GiB total, 2.6 GiB used, 5.1 GiB available,
   no swap. Current top containers: reporting-worker 107.2 MiB/768 MiB, central-api
   104.3 MiB/1 GiB, coolify 356.4 MiB, openclaw 651.7 MiB. **The ~+1 GiB of new services
   (prefect-server + prefect-postgres + backup) fits comfortably — the §9 headroom check
   passes.** Note the worker's 107 MiB reading is far below Kodee's earlier 605 MiB measurement —
   consistent with an idle/restarted worker vs one carrying live ephemeral-server subprocesses;
   capture the Phase-0 per-process breakdown during an active run to confirm.
2. **Before changes (Phase 0 evidence):** inside the reporting-worker container during an active
   run, capture `ps -o pid,rss,cmd` (worker vs uvicorn subprocesses) plus `docker stats` samples;
   the sum of current limits is 5.3 GB across 6 services today.
3. **After Phase 1–2 on staging/local compose:** 24 h soak with the operations feed active;
   sample RSS every 60 s for worker, prefect-server, prefect-postgres; drive ≥3 manual runs +
   1 force refresh + the 07:00 scheduled run.
4. **Set limits = p99 RSS × 1.4, rounded to 64 MiB**; floors: worker 384 MiB, server 512 MiB,
   postgres 256 MiB. VPS fit is confirmed by the July 15 evidence above; re-verify at deploy time.

## 6. Failure handling matrix

| Failure | Behavior |
|---|---|
| Prefect server down/unreachable | Worker health probe skips claiming; rows stay `requested`; `orchestrator_healthy=false`; UI "unavailable"; readiness fails via `reporting_progress` after the stale window. Mid-run failure → `ORCHESTRATION_FAILED`, `retryable`, backoff; previous report stays visible. |
| Worker wedged (any hang) | Continuous lease renewal keeps healthy long runs alive; the `REPORTING_RUN_TIMEOUT_SECONDS` watchdog exits the process for true hangs; `restart: on-failure` restarts; lease sweep reclaims within ≤10 min; bounded DB/boto/Prefect timeouts make hangs rare. |
| Expired lease | Unchanged: dispatcher `recover_stale_runs` → `retryable`/`STALE_ABANDONED` (or `failed` at max attempts); CAS token + in-transaction verification block zombie publication. |
| SIGTERM (deploy) | Unchanged stop-Event + 15 m grace; in-flight run finishes or is reclaimed by lease expiry after the container is gone. |
| Deployment overlap (two workers briefly) | Unchanged: single-active partial unique index + advisory lock + claim CAS; second claimer idles. |
| Retry exhaustion | `failed`/`MAX_ATTEMPTS_EXCEEDED`; UI failure notice with safe `error_code`; operator re-runs via "Run now"/"Force refresh"; runbook triage. |
| R2 absent/down | Unchanged: caching/persistence/backups disabled or treated as miss; never fails a run. |
| Prefect DB lost | No business work lost (PG queue authoritative); task-level history/recovery lost; restore from R2 backup per runbook. |

## 7. Phased implementation (one local commit per phase)

**Phase 0 — Immediate containment (operator actions, no commit):**
capture evidence (process/RSS breakdown, Prefect log excerpts around the 422s/port collisions,
queue-row timeline incl. whether the stale sweep fired); then restart `reporting-worker` in
Coolify (safe: durable queue, SIGTERM-clean). Expect the backlog to drain or fail fast with
logged orchestration errors — either outcome sharpens the diagnosis. No DB mutation, no config
change.

**Phase 1 — Dedicated Prefect server and database wiring (commit 1):**
`prefect-postgres` + `prefect-server` Compose services (pinned `PREFECT_SERVER_IMAGE`,
`PREFECT_API_DATABASE_CONNECTION_URL`, `pg_trgm` init, healthchecks), `PREFECT_API_URL` +
request timeout in both workers, SQLite-fallback guard script, PIPELINE_DESIGN amendment.
Verify locally: full stack up; one manual run end-to-end; Prefect tables present in
prefect-postgres; no `SubprocessASGIServer` in logs.

**Phase 2 — Execution robustness (commit 2):**
Runner lifecycle refactor (`claim_next` / `execute_claim_with_renewal` / `finalize_claim`),
continuous lease-renewal thread (remove `renew_pipeline_lease` task), Prefect run correlation
(`prefect_flow_run_id` + deterministic run name + startup orphan reconciliation), stage-progress
stamping, `ORCHESTRATION_FAILED`/`INTERNAL_FAILED` taxonomy, migration 0010, watchdog, DB/boto
timeouts, `last_progress_at` + orchestrator-health stamping, health.py readiness. Verify: kill
prefect-server mid-run → `retryable ORCHESTRATION_FAILED`; blocked-executor test → watchdog exit,
clean reclaim, and orphaned Prefect run closed on restart.

**Phase 3 — R2 result persistence, retention, and backups (commit 3):**
Optional `persist_result` to R2 on the transformation task, Prefect run retention task
(maintenance worker, API-only), dedicated `prefect-db-backup` service (`pg_dump` from a pinned
postgres image, least-privilege `PREFECT_BACKUP_R2_*` credentials, disk sampling), restore
procedure in runbook. Verify: with R2 absent everything still runs; with R2 present, persisted
results and backups appear under their dedicated prefixes and a restore drill passes.

**Phase 4 — Operator UX, resource measurement, deployment verification (commit 4):**
Reporting API `queue_state` + worker fields, Back Office states, runbook (stuck/unavailable/
retry-exhausted/restore triage + the approval-gated Prefect upgrade procedure), deploy-workflow
verification additions (SQLite-fallback guard, client/server version check), soak-derived
resource limits, memory-bank `progress.md`/`techContext.md` updates, production acceptance
checklist.

## 8. Tests & production acceptance gates

- **Unit/integration (existing suites, extended):** taxonomy mapping (Prefect client error →
  `ORCHESTRATION_FAILED`; unknown → `INTERNAL_FAILED`; SQLAlchemy → `DB_UNAVAILABLE`; both new
  codes retryable); runner lifecycle refactor parity (`run_once` composition preserves every
  existing state-machine test); continuous-renewal thread (long single stage keeps lease; CAS
  loss sets abort; zombie publication still blocked; **a renewing lease with a hung stage still
  fails readiness**); run correlation (flow-run ID persisted token-CAS-guarded; deterministic
  name; startup reconciliation closes an orphaned Prefect run); readiness matrix (idle-progress
  fresh/stale × running-stage within/over deadline × orchestrator healthy/unhealthy × heartbeat
  fresh/stale); API `queue_state` derivation; UI rendering for all six states (Vitest);
  queue/lease/CAS tests unchanged and green; compose config validation in release checks.
- **Watchdog kill matrix (required):** induced `os._exit` during extract, during transform, and
  during load must each show: advisory lock released (connection death frees it), open
  transaction rolled back (no partial rows), stale-lease recovery to `retryable`, no zombie
  publication after restart, and Prefect flow-run state reconciled/abandoned cleanly on the
  dedicated server after the worker returns.
- **CI integration smoke (data project):** one flow run against a real `prefect server start` +
  Postgres service container pinned to the same version; assert no ephemeral fallback
  (`PREFECT_API_URL` set + log scan for `SubprocessASGIServer`) and assert Prefect tables live in
  Postgres (the SQLite-fallback guard, exercised in CI).
- **Soak (pre-production gate):** 24 h per §5 with feed active; gates: p99 RSS within budget,
  zero `ORCHESTRATION_FAILED`/`INTERNAL_FAILED`, zero watchdog exits, scheduled run fires once at
  07:00 America/Chicago, cache hit on an unchanged rerun within 1 h, a deliberately slow (>10 min)
  run survives via continuous renewal without reclamation.
- **Production acceptance:** one approved release deploy; readiness green; SQLite-fallback guard
  passes; one manual + next scheduled run succeed; induced outage — stop prefect-server 5 min →
  UI "unavailable", queued work waits, automatic recovery; 48 h memory sampling with ≥30%
  headroom; image-rollback drill (previous `TRACKFLOW_IMAGE_TAG` only; Prefect server untouched)
  with reporting still functioning; one Prefect-DB restore drill; no stuck `running` rows older
  than lease + sweep interval at any point.

## 9. Migration/compatibility risks & non-goals

Risks: DB setting verified supported at 3.7.8 (`PREFECT_API_DATABASE_CONNECTION_URL`, plus
`PREFECT_API_URL`/`PREFECT_API_REQUEST_TIMEOUT` — reviewer-confirmed); the SQLite-fallback guard
still runs as defense-in-depth; old-image serialization of new error codes (verify/widen schema,
§4); Prefect server schema migration behavior (pin + document); client-vs-server version skew
(server-first rule, digest-pinned server image, deploy-time version check); VPS memory headroom
(blocking check, §5); Coolify handling of the two new named-volume services; R2-absent
deployments run without Prefect backups (documented, logged); runner refactor regression risk
(mitigated by keeping `run_once` as a composition and the untouched state-machine test suite).

Non-goals: no Prefect Cloud; no work-pool dispatch (dual-authority conflict — revisit only if the
PG-queue authority is ever relaxed); no queue/lease redesign beyond continuous renewal; no change
to `telemetry_events` or best-effort semantics; no DB downgrade paths; cache correctness stays in
`cache.py` (Prefect result persistence is recovery optimization/diagnostics, never authority);
no UI redesign/charting; no Supabase-hosted Prefect state.

## 10. Additional production evidence needed before finalizing limits

~~VPS total/available RAM and current real usage~~ (obtained July 15 — §5); per-process RSS
inside today's worker **during an active run**; the exact
log sequence around one 422 (confirms the SQLite/subprocess inference); whether the stale sweep
transitioned the stuck run after lease expiry (confirms or refutes the wedged-loop inference);
report-run duration distribution (sets `REPORTING_RUN_TIMEOUT_SECONDS` and the readiness progress
window); Supabase pooler connection headroom (Prefect state does not touch Supabase; the worker
adds only its health-probe pattern).

## Verification

Per phase: data-project suite (`uv run --project data pytest`), central-api suite with disposable
Postgres + `alembic upgrade head`, backoffice `type-check`/`test`/`build`, and
`docker compose config -q` on both compose files. End-to-end: full local compose stack; one
manual run via the Back Office button; one CLI run; one induced prefect-server outage; one
SIGTERM during a run; the watchdog kill matrix — all queue rows must reach a terminal or
claimable state with truthful `error_code`s, and `/api/health` must track processing ability
throughout.
