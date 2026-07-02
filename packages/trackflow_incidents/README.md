# `packages/trackflow_incidents/`

Shared Python contracts for TrackFlow's incident domain.

The package owns the canonical incident enums, legacy customer-service CSV
validation, and normalization into the Central API incident shape. It never
stores or returns customer email values. Both the historical Incident Report
Processor and the Central API seed command consume this package.

The production CSV is sensitive and must not be read during development or
tests. Use `services/incident-processor/tests/fixtures/sample-incidents.csv`.

