# `data/`

Data engineering assets for the TrackFlow platform.

| Folder | Purpose |
|---|---|
| `raw/` | Source data: exports, dumps, sample files, untransformed datasets |
| `process/` | Pure, deterministic business-performance transformations |
| `pipelines/` | Pipeline orchestration package (runner/flows arrive in later approved phases) |
| `eval/` | AI evaluation datasets for testing agent and model outputs |

Engagement 6 Phase 4 establishes an isolated `trackflow-data-pipelines` uv project. The first
implemented capability is the in-memory weekly warehouse/client KPI transform under
`process/business_performance/`; it has no database, Prefect server, or external-service dependency
at runtime.

```bash
uv run --project data --extra dev ruff check data/pipelines data/process tests/pipelines
uv run --project data --extra dev mypy --config-file data/pyproject.toml data/pipelines data/process
uv run --project data --extra dev pytest -c data/pyproject.toml tests/pipelines \
  --cov=pipelines --cov=process --cov-config=data/pyproject.toml --cov-report=term-missing
uv build --project data
```
