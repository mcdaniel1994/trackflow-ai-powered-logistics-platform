# Weekly warehouse and client performance

This package owns the durable PostgreSQL queue, Dallas dispatcher, single-concurrency runner,
in-process Prefect execution, durable hourly SQL rollups, exact reconciliation, and the legacy
optional private R2 transform cache.

Production runs `python -m pipelines.business_performance.worker` as one always-on, read-only
Compose service. It polls every five seconds, records a worker heartbeat every ten seconds, and
checks the America/Chicago schedule every minute. Queue leases, claim-token comparisons,
idempotent scheduled requests, retries, and the PostgreSQL advisory lock remain authoritative.
The Phase 6.1 reliability image `13bba2e` and Alembic revision `20260728_0011` are deployed; the
owner closed its remaining exercises by documented exception. Phase 6.2 is deployed through
additive revision `20260728_0012`; its set-based 113,064-row publication correction awaits
redeployment and live reconciliation. `REPORTING_HOURLY_ROLLUPS_ENABLED` defaults off: the legacy
07:00 path remains byte-compatible while disabled. When explicitly enabled for shadow validation,
Prefect computes completed UTC hours at 07:00 and 19:00 America/Chicago, recomputes an unconditional
trailing 72 hours, writes only `reporting.hourly_activity_rollups`, and leaves weekly served data
unchanged.
Prefect clients use the private dedicated Prefect Server at `http://prefect-server:4200/api`;
that server stores orchestration state in its own PostgreSQL 16 volume. The TrackFlow queue remains
the only dispatch authority: no work pool or Prefect-managed schedule claims business work.
Prefect home directories remain beneath `/tmp`, analytics/telemetry settings are disabled, and a
completely absent R2 configuration disables cache reuse without disabling reports.

Failures cross the Prefect boundary and also transition the durable queue with only run ID,
attempt, stage, fixed error code, and exception type in logs. SQL, records, credentials, and
exception messages are never logged.

Run aggregate-only exact reconciliation at a reviewed fixed cutoff:

```bash
uv run --project data python -m pipelines.business_performance.rollups \
  --start 2026-07-01T00:00:00Z --cutoff 2026-07-28T18:00:00Z
```

Any future mutable source or back-dated insert outside the trailing 72-hour window requires
dirty-bucket tracking before rollout.
