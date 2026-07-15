# `data/pipelines` folder

This folder groups **all data pipelines in the monorepo** related to the company: ingestion, ETL/ELT, cleaning, transformation, and loading into analytical or production systems.

Each subfolder or file under `data/pipelines/` should represent **one pipeline or job set** (for example `sales-etl`, `telemetry-stream`, `customer-segmentation`) and include the required configuration (scripts, orchestration, connectors, schemas, etc.).

- **Main purpose**: consolidate in one place the data movement and transformation logic that powers the company’s applications and analytics.
- **Recommendation**: document pipelines as you add them—their goal, data sources and sinks, dependencies, and how to run them in development, testing, and production.

Engagement 6 Phase 6 completes the local pipeline execution path under `business_performance/`:
Prefect-as-library extraction/transform/load/finalization flows, transactional publication, and a
one-hour application-managed S3-compatible cache selected by the documented GATE-8a spike. The
durable queue remains PostgreSQL-owned, KPI business logic remains in the pure `data/process/`
layer, and absent R2 configuration safely disables caching.
The production Compose stack runs one long-lived worker instead of separate Coolify cron jobs;
its writable Prefect state is isolated under `/tmp` in an otherwise read-only container.
