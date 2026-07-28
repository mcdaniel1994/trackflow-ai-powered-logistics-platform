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
additive revision `20260728_0012` and owner-accepted after corrected publication, exact
reconciliation, and runtime-budget evidence. Phase 6.3 is deployed through `20260728_0013` and
owner-accepted by explicit exception after rollback drill one passed; drill two and the seven-day
observation were waived, not executed. Phase 6.4 direct-executor work is approved to begin, while
the production swap, resource-limit changes, final Prefect removal, and time-gate exceptions remain
separately owner-gated.
The active executor now always computes completed UTC-hour rollups at 07:00 and 19:00
America/Chicago and recomputes an unconditional trailing 72 hours; the legacy raw Python/R2
transform is no longer reachable from the executor. `REPORTING_ROLLUP_CUTOVER_ENABLED` still
defaults off. When enabled, the load transaction reconciles the fixed snapshot, publishes complete
weeks, and atomically advances the active version. Reads then use weekly facts for completed
history and hourly facts for the current incomplete week.
Prefect clients use the private dedicated Prefect Server at `http://prefect-server:4200/api`;
that server stores orchestration state in its own PostgreSQL 16 volume. The TrackFlow queue remains
the only dispatch authority: no work pool or Prefect-managed schedule claims business work.
Prefect home directories remain beneath `/tmp`, analytics/telemetry settings are disabled, and a
completely absent R2 configuration disables cache reuse without disabling reports.

Failures cross the Prefect boundary and also transition the durable queue with only run ID,
attempt, stage, fixed error code, and exception type in logs. SQL, records, credentials, and
exception messages are never logged.

`REPORTING_COMPUTATION_ENABLED=false` keeps the worker healthy but stops claims and makes reporting
reads return a stable safe 503. `REPORTING_FORCE_STALE=true` is the explicit rollback to the last
verified active snapshot when the control plane is unavailable; it never re-enters the legacy
transform or raw-source read path. Inner SQL retries are limited to an explicit connectivity
allowlist.

Run aggregate-only exact reconciliation at a reviewed fixed cutoff:

```bash
uv run --project data python -m pipelines.business_performance.rollups \
  --start 2026-07-01T00:00:00Z --cutoff 2026-07-28T18:00:00Z
```

Any future mutable source or back-dated insert outside the trailing 72-hour window requires
dirty-bucket tracking before rollout.
