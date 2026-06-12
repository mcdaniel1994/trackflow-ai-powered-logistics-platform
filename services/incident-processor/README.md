# `services/incident-processor/`

FastAPI service and shared Python package for the TrackFlow Incident Report Processor subproject.

This is not Engagement 5. The Central API remains reserved for a future engagement under `services/central-api/`.

## Runtime

```bash
uv run --project services/incident-processor uvicorn incident_processor.main:app --reload
```

The API exposes:

- `GET /health`
- `POST /api/incidents/analyze`
- `GET /api/incidents/results/export`

## CLI

The same package powers the root CLI wrapper:

```bash
python scripts/analyze.py scripts/incidents-trackflow.csv
uv run --project services/incident-processor analyze scripts/incidents-trackflow.csv
```

`scripts/incidents-trackflow.csv` is intentionally ignored because it can contain customer email addresses.

## In-Memory Results

The API stores the latest aggregate analysis in one `app.state` slot. This is demo-grade storage:

- last-write-wins
- cleared on restart
- intended for one worker only

## CORS

Set `INCIDENT_PROCESSOR_CORS_ORIGINS` to a comma-separated allowlist. Defaults:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

## Tests

```bash
uv run --project services/incident-processor --extra dev pytest
```

The synthetic fixture lives at `tests/fixtures/sample-incidents.csv` and uses fake `example.com` addresses.
