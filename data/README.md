# `data/`

Data engineering assets for the TrackFlow platform.

| Folder | Purpose |
|---|---|
| `raw/` | Source data: exports, dumps, sample files, untransformed datasets |
| `process/` | Pure, deterministic business-performance transformations |
| `pipelines/` | Durable queue, dispatcher, runner lifecycle, and later ETL orchestration |
| `eval/` | AI evaluation datasets for testing agent and model outputs |

Engagement 6 establishes an isolated `trackflow-data-pipelines` uv project. Phase 5 adds a durable
PostgreSQL queue, America/Chicago dispatcher, lease/CAS state machine, and advisory-lock-protected
runner lifecycle alongside the pure weekly KPI transforms. Phase 6 supplies the in-process Prefect
ETL executor and an optional one-hour S3-compatible cache. The July 15 owner-approved amendment
adds a private Prefect Server backed by dedicated PostgreSQL for stable orchestration state without
adding work-pool dispatch; absent cache configuration preserves full correctness.
Production hardening adds the always-on `business_performance.worker`: it polls every five
seconds, heartbeats every ten seconds, checks the Dallas schedule every minute, and continues to
use PostgreSQL leases, claim tokens, idempotency, and advisory locking. The second remediation
phase adds independent continuous lease renewal, token-CAS flow-run/stage correlation, fail-closed
Prefect health, startup orphan reconciliation, bounded I/O timeouts, and a hard run watchdog. Phase 3
adds optional Prefect recovery results under `prefect-results/recovery`, API-only terminal-run
retention, and an isolated read-only PostgreSQL backup service with a distinct R2 token. Phase 4
adds shared server-derived queue/readiness states and startup gates that verify Prefect PostgreSQL
state plus the digest-mapped server/client version contract before the worker can claim work.

```bash
uv run --project data --extra dev ruff check data/pipelines data/process tests/pipelines
uv run --project data --extra dev mypy --config-file data/pyproject.toml data/pipelines data/process
uv run --project data --extra dev pytest -c data/pyproject.toml tests/pipelines \
  --cov=pipelines --cov=process --cov-config=data/pyproject.toml --cov-report=term-missing
uv build --project data
```

Run one explicit recomputable week directly against a migrated local database:

```bash
uv run --project data python data/pipelines/pipeline.py --week-start 2026-07-13
```
