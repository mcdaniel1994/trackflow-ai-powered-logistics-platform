# `scripts` folder

This folder contains **helper scripts** for the monorepo: development automation, maintenance utilities, repetitive tasks (setup, lint, migrations, data generation, etc.), and internal tooling.

- **Main purpose**: group support tools that do not belong to a specific app, agent, or pipeline but make the team’s work easier.
- **Recommendation**: document each script (what it does, parameters, requirements, usage examples) and keep them reproducible (and safe) across environments.

## Centralized Incident Seed

`seed_incidents.py` is a thin wrapper around Central API's idempotent historical
import. Use the synthetic fixture for development:

```bash
uv run --project services/central-api python scripts/seed_incidents.py \
  services/central-api/tests/fixtures/sample-incidents.csv
```

The command prints aggregate inserted/skipped/invalid counts only. Access to the
real CSV requires explicit authorization under the sensitive-dataset rule.
