# Incident Report Processor Retirement

The standalone Incident Report Processor was retired in July 2026 after the
Centralized Incident Manager became the authoritative incident workflow in
`services/central-api/`.

Retired paths:

- `services/incident-processor/`
- `scripts/analyze.py`

The synthetic legacy-import fixture moved to
`services/central-api/tests/fixtures/sample-incidents.csv`. Shared privacy-safe
CSV validation remains in `packages/trackflow_incidents/`, and the explicit
development-only import command remains in Central API.

Production incidents start empty. Historical code remains available in git
history; it must not be recreated as an active service.
