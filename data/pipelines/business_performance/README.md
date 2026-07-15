# Weekly warehouse and client performance

This package owns the durable PostgreSQL queue, Dallas 07:00 dispatcher, single-concurrency
runner, in-process Prefect extract/transform/load flow, and optional private R2 transform cache.

Production runs `python -m pipelines.business_performance.worker` as one always-on, read-only
Compose service. It polls every five seconds, records a worker heartbeat every ten seconds, and
checks the America/Chicago schedule every minute. Queue leases, claim-token comparisons,
idempotent scheduled requests, retries, and the PostgreSQL advisory lock remain authoritative.
Prefect clients use the private dedicated Prefect Server at `http://prefect-server:4200/api`;
that server stores orchestration state in its own PostgreSQL 16 volume. The TrackFlow queue remains
the only dispatch authority: no work pool or Prefect-managed schedule claims business work.
Prefect home directories remain beneath `/tmp`, analytics/telemetry settings are disabled, and a
completely absent R2 configuration disables cache reuse without disabling reports.

Failures cross the Prefect boundary and also transition the durable queue with only run ID,
attempt, stage, fixed error code, and exception type in logs. SQL, records, credentials, and
exception messages are never logged.
