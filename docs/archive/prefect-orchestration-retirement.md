# Retirement Note: Dedicated Prefect Orchestration

**Engagement:** 6 — Data Pipelines & Telemetry (`docs/briefs/06-data-pipelines-telemetry.md`)
**Specification:** `docs/planning/remaining_planning/spec.md` §7.2 (Phase 6.4)
**Original paths:**
`data/pipelines/business_performance/{flows,cache,prefect_version,startup_guard}.py`,
`services/central-api/scripts/{prefect_db_backup,prefect_version_guard,prune_prefect_runs}.py`,
`scripts/release/verify_prefect_contract.py`, `docker/prefect-*`
**Replaced by:** `data/pipelines/business_performance/direct_executor.py`, running inside the
existing `reporting-worker` container
**Retired:** August 2026

## What the dedicated-Prefect architecture delivered

Engagement 6 originally ran the weekly business-performance pipeline through a self-hosted Prefect
Server backed by its own private PostgreSQL. That architecture was not decorative — it was hardened
substantially over its life and delivered real guarantees:

- private Prefect Server / PostgreSQL wiring with no public exposure, and a SQLite-fallback guard
  that refused to start against an ephemeral state store;
- independent claim renewal, and token-guarded run/stage correlation through
  `pipeline_runs.prefect_flow_run_id`;
- fail-closed orchestrator health, orphan-run reconciliation, and a hard run watchdog;
- optional R2 recovery results, API-only retention, and an isolated read-only database backup
  service under a dedicated `prefect_backup` role;
- six server-derived operator states and release startup guards.

Those guarantees are the reason the pipeline became reliable. They are preserved in behaviour: every
one of them that protects *TrackFlow* data — claim-token CAS, lease renewal, stale-lease recovery,
advisory-lock single-publisher enforcement, stage recording, the run watchdog, the durable queue —
lives in PostgreSQL and the worker, not in Prefect, and is unchanged by this retirement.

## Why it was retired

Phase 6.4 of the approved specification identified that Prefect owned only the last row of the
execution model: it executed runs that PostgreSQL and the worker had already claimed, scheduled,
leased, and would finalize. Everything else was already TrackFlow's. §7.2 therefore specified a
direct SQL executor satisfying the same `RunExecutor` contract, swapped in behind
`REPORTING_EXECUTOR`, followed by removal of the orchestrator.

The direct SQL executor was swapped into production under owner approval, verified against the
Prefect path on identical fixed-cutoff rollups, and had been serving production reporting on its own
for weeks before this removal. During that period Prefect executed nothing.

Two further facts made removal the correct call rather than an optional cleanup:

1. **It was failing anyway.** By August 2026 `prefect-server` could no longer reach
   `prefect-postgres` at all — repeated `asyncpg` connect timeouts crashing its internal
   `pause_expirations` service — and had been crash-looping. Nothing depended on it, so nothing
   alerted.
2. **It cost real capacity.** Six containers plus a volume ran continuously on a single-VPS Coolify
   host shared with the entire application, and the Prefect runtime pulled 71 transitive Python
   packages into the data image and 59 into the Central API image.

## Acceptance evidence

Per §7.2 "Verification before removal":

| Requirement | Status |
|---|---|
| Direct executor produces identical rollups on the same fixed cutoff | Verified before the production swap; the parity test compared both executors on a fixed cutoff until Prefect was removed |
| Scheduled execution, manual trigger, retry/backoff, lease renewal, worker-restart and stale-lease recovery exercised in production | Exercised during the Phase 6.4 production swap |
| 7-day clean-run period (D-1) | **Waived by the owner**, together with the Phase 6.4 48-hour studies. Recorded here as waived — not executed, not passed |
| Owner approval for removal | Given August 20, 2026 |

The direct executor then ran production reporting well beyond seven days in practice, though not as
the specified controlled observation.

## What was kept

- **`reporting-worker` remains its own container and its own failure domain**, as §7.2 requires.
- **`pipeline_runs.prefect_flow_run_id` is retained** as a nullable historical column and was **not**
  dropped. It correlates runs executed before this retirement. Nothing writes it now.
- **`REPORTING_EXECUTOR` is still read and still fails closed.** `direct_sql` is the only accepted
  value; a deployment left pinned to `prefect` raises rather than silently falling back. Guarded by
  `tests/pipelines/business_performance/test_executor_selection.py`.
- **The release startup verification** (`scripts/verify_reporting_startup.py`) is unchanged in
  substance: it still proves the worker reached its poll loop and heartbeated past the deployment
  boundary. Only its Prefect framing was removed.

## What was removed

| Removed | Notes |
|---|---|
| `prefect-server`, `prefect-postgres`, `prefect-postgres-bootstrap`, `prefect-postgres-guard`, `prefect-version-guard`, `prefect-db-backup` | From `compose.yaml` and `compose.coolify.yaml`, with the `prefect-db` volume |
| `flows.py` | `prefect_executor`, the flow/task graph, `reconcile_orphaned_flow_runs` |
| `cache.py` | Prefect result storage and the R2 transformation cache — imported only by `flows.py`. The `REPORTING_R2_*` environment went with it |
| `startup_guard.py`, `prefect_version.py` | Guarded a runtime that no longer exists |
| `prune_prefect_runs.py` | Prefect-API retention; TrackFlow retention in `maintenance_worker.py` is unaffected |
| `prefect_db_backup.py`, `docker/prefect-*` | Backup service, roles, and images for the retired database |
| `verify_prefect_contract.py` | Release gate; the compose syntax validation it also performed was kept |
| `queue.record_prefect_flow_run` | The only writer of the retained historical column |
| `worker.prefect_is_healthy`, `orchestrator_health`, `reconcile_prefect_runs` | Direct SQL executes in-process; the worker is its own orchestrator |
| `prefect>=3`, `prefect-aws` | 71 transitive packages out of `data/uv.lock`, 59 out of `services/central-api/uv.lock` |

A regression guard, `test_no_prefect_surface_remains_in_deployment` in
`services/central-api/tests/test_reporting_deployment.py`, fails if any Prefect reference returns to
either Compose file or to `docker/`.

## Recovering the history

The removed code is recoverable from git history prior to the retirement commit. The design record
lives in `docs/planning/reporting-dedicated-prefect-architecture.md` and
`docs/archive/agent_implementation_plans/2026-07-15-engagement-6-reporting-dedicated-prefect-architecture.md`,
and the rationale for the replacement is `docs/planning/remaining_planning/spec.md` §7.

Per `AGENTS.md` "Preserving Milestone Work", the completed work is preserved through this note and
git history — not by keeping unused code on disk.

## Operator action after this change

The six Prefect containers and the `prefect-db` volume are no longer in the Compose files, so a
redeploy stops and removes them. The following Coolify environment variables become unused and can
be deleted: `PREFECT_SERVER_IMAGE`, `PREFECT_DB_PASSWORD`, `PREFECT_GUARD_DB_PASSWORD`,
`PREFECT_BACKUP_DB_PASSWORD`, `PREFECT_BACKUP_R2_*`, `PREFECT_BACKUP_RETENTION_DAYS`,
`PREFECT_DB_DISK_WARNING_MB`, `PREFECT_API_REQUEST_TIMEOUT`, `PREFECT_GUARD_TIMEOUT_SECONDS`,
`PREFECT_RUN_RETENTION_DAYS`, and `REPORTING_R2_*`.
