# `data/pipelines` folder

`database.py` provides the shared bounded-pool diagnostics and session advisory-lock lifecycle
helpers for the October 15 Engagement 6 connection correction. Backend verification passed locally;
dashboard recovery also passed local acceptance. The owner approved commit/push; production rollout remains pending.

This folder groups **all data pipelines in the monorepo** related to the company: ingestion, ETL/ELT, cleaning, transformation, and loading into analytical or production systems.

Each subfolder or file under `data/pipelines/` should represent **one pipeline or job set** (for example `sales-etl`, `telemetry-stream`, `customer-segmentation`) and include the required configuration (scripts, orchestration, connectors, schemas, etc.).

- **Main purpose**: consolidate in one place the data movement and transformation logic that powers the company’s applications and analytics.
- **Recommendation**: document pipelines as you add them—their goal, data sources and sinks, dependencies, and how to run them in development, testing, and production.

Engagement 6 completes the pipeline execution path under `business_performance/`: direct SQL
extraction, transformation, load, and finalization, with transactional publication. The durable
queue remains PostgreSQL-owned and KPI business logic remains in the pure `data/process/` layer.
The production Compose stack runs one long-lived worker instead of separate Coolify cron jobs. The
TrackFlow PostgreSQL queue is authoritative and the read-only worker keeps only temporary files
under `/tmp`.
Phase 6.3 removed the raw Python transform from the active executor, atomically activates only
exactly reconciled rollups, and serves completed history from weekly facts plus the current
incomplete week from hourly facts.
Phase 6.4 replaced the Prefect executor with `direct_sql`, which runs inside the reporting worker
against PostgreSQL only. `REPORTING_EXECUTOR` remains an allowlisted selector that fails closed;
`direct_sql` is its one accepted value. Prefect was retired in August 2026 — see
`docs/archive/prefect-orchestration-retirement.md`.

Engagement 11 adds opt-in public-support options to `rag.py`: bounded I/O with no retries,
English/Spanish answer selection and untrusted conversational context. Current retrieved passages
supply facts. Caller configuration pins the isolated public collection; existing internal callers
retain their behavior. No public content or history is stored by this package.
