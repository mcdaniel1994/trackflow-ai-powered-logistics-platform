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
Reporting-reliability Phase 6.1 adds durable per-attempt history, bounded status evidence, fixed
timeouts, exact-once failure accounting, and owner-approved persistent-log defaults; it is deployed
and closed by documented owner exception. Phase 6.2 adds off-by-default durable hourly SQL rollups,
fixed cutoffs, trailing 72-hour recomputation, exact reconciliation, and a 12-hour shadow cadence.
It is deployed through Alembic `20260728_0012` and production-accepted. Phase 6.3 adds atomic
reconciled weekly publication, weekly/history plus hourly/current-week reads, transient-only inner
SQL retries, an explicit computation kill switch, and verified-stale serving mode. It is locally
verified and deployed through `20260728_0013`. Rollback drill one passed; the owner accepted Phase
6.3 by explicit exception and waived drill two and the seven-day observation without executing
them. The Phase 6.4 time gates were explicitly waived rather than passed or executed, and the
production direct-executor swap was separately approved. The implementation adds a direct SQL
executor with unconditional stage CAS,
transient-only bounded retries, abort handling, and fixed-cutoff Prefect/direct parity coverage.
The shared SQL path also passes the disposable 2.12-million-row budget gate. Production Compose
selects it; Prefect remains the code/local default and a rollback topology pending separate final
removal approval. Evidence: `docs/planning/engagement-6.4-phase-review-2026-07-28.md`.

Independent sales-forecasting Phases 6.5.a–b live under `process/sales_forecasting/`. They consume the
generated, deterministic 120-month dataset in `raw/trackflow_sales.csv` only in an explicit offline
environment, train a fixed-seed strict-recursive Random Forest, run five-fold expanding-window
evaluation over the training partition only, and write versioned artifacts to `eval/`. The formal
evaluation diagnoses overfitting and does not approve operational use. The owner accepted
Phases 6.5.a–b as a complete offline evaluation on 2026-07-28; the model remains prohibited from
serving and operational use. Forecasting/ML packages are optional and are absent from the
production Central API virtualenv.

Engagement 8 Phase 5 extends `pipelines/rag.py` with an opt-in structured generation result so the
agent can produce one guarded answer and, normally, no memory candidate in the same mocked/provider
call. The ordinary RAG `query()` contract remains a plain string. Candidate persistence and all
human-decision enforcement remain Central API responsibilities; the data package never stores
conversation or memory content. The current full data gate is 180 passing tests, one skipped, and
90.94% branch-aware source coverage.

```bash
uv run --project data --extra dev ruff check data/pipelines data/process tests/pipelines
uv run --project data --extra dev mypy --config-file data/pyproject.toml data/pipelines data/process
uv run --project data --extra dev pytest -c data/pyproject.toml tests/pipelines \
  --cov=pipelines --cov=process --cov-config=data/pyproject.toml --cov-report=term-missing
uv build --project data
```

Run the opt-in Phase 6.2 production-volume gate only against the disposable local PostgreSQL on
`127.0.0.1:55432`; it loads and then removes 2.12 million deterministic source/event rows:

```bash
REPORTING_PERFORMANCE_TEST=1 uv run --project data --extra dev pytest \
  -c data/pyproject.toml tests/pipelines/test_rollup_performance.py -q -s
```

Validate and reproduce the complete Phase 6.5 offline artifacts:

```bash
uv run --project data --extra forecasting --extra dev python scripts/generate_trackflow_sales.py --check
uv run --project data --extra forecasting --extra dev python scripts/train_sales_forecast.py --evaluate --force
uv run --project data --extra forecasting --extra dev pytest tests/pipelines/test_sales_forecasting.py
```

Run one explicit recomputable week directly against a migrated local database:

```bash
uv run --project data python data/pipelines/pipeline.py --week-start 2026-07-13
```
