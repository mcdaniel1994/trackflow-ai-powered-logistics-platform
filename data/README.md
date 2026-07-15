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
runner lifecycle alongside the pure weekly KPI transforms. Phase 6 supplies the Prefect-as-library
ETL executor and an optional one-hour S3-compatible cache; no permanent Prefect server or external
service is introduced, and absent cache configuration preserves full correctness.

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
