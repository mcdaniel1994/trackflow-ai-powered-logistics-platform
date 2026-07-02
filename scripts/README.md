# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

## Incident Report Processor

`analyze.py` is the command-line entry point for the Incident Report Processor subproject. It delegates validation, analysis, formatting, and export logic to the importable Python package in `services/incident-processor/`.

Supported usage after the Python project has been installed or synced:

```bash
python scripts/analyze.py scripts/incidents-trackflow.csv
uv run --project services/incident-processor analyze scripts/incidents-trackflow.csv
```

The official incident CSV belongs at `scripts/incidents-trackflow.csv`. That path is ignored because the file can contain real customer email addresses.

## Centralized Incident Seed

`seed_incidents.py` is a thin wrapper around Central API's idempotent historical
import. Use the synthetic fixture for development:

```bash
uv run --project services/central-api python scripts/seed_incidents.py \
  services/incident-processor/tests/fixtures/sample-incidents.csv
```

The command prints aggregate inserted/skipped/invalid counts only. Access to the
real CSV requires explicit authorization under the sensitive-dataset rule.
