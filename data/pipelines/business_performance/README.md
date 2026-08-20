# Weekly warehouse and client performance

This package owns the durable PostgreSQL queue, Dallas dispatcher, single-concurrency runner,
in-process direct SQL execution, durable hourly SQL rollups, and exact reconciliation.

Production runs `python -m pipelines.business_performance.worker` as one always-on, read-only
Compose service. It polls every five seconds, records a worker heartbeat every ten seconds from a single
writer, and checks the America/Chicago schedule every minute. Polling itself does not write:
the heartbeat row is written by the periodic beat and on an orchestrator-health transition
only, which is what keeps steady-state database write volume flat. Queue leases, claim-token comparisons,
idempotent scheduled requests, retries, and the PostgreSQL advisory lock remain authoritative.
The Phase 6.1 reliability image `13bba2e` and Alembic revision `20260728_0011` are deployed; the
owner closed its remaining exercises by documented exception. Phase 6.2 is deployed through
additive revision `20260728_0012` and owner-accepted after corrected publication, exact
reconciliation, and runtime-budget evidence. Phase 6.3 is deployed through `20260728_0013` and
owner-accepted by explicit exception after rollback drill one passed; drill two and the seven-day
observation were waived, not executed. Phase 6.4 replaced the Prefect executor with `direct_executor.py`, which implements the same
engine/claim/abort contract with unconditional stage CAS, abort checks, transient-only bounded
retries, and token-verified publication. It was verified against the Prefect path on identical
fixed-cutoff rollups before the owner-approved production swap, and Prefect was retired in August
2026 (`docs/archive/prefect-orchestration-retirement.md`). The specified 48-hour studies and
seven-day clean run were waived by the owner, not executed. The SQL path passes the existing
disposable 2.12-million-row performance gate.
The active executor always computes completed UTC-hour rollups at 07:00 and 19:00
America/Chicago and recomputes an unconditional trailing 72 hours. `REPORTING_ROLLUP_CUTOVER_ENABLED` still
defaults off. When enabled, the load transaction reconciles the fixed snapshot, publishes complete
weeks, and atomically advances the active version. Reads then use weekly facts for completed
history and hourly facts for the current incomplete week.
The TrackFlow queue is the only dispatch authority, and execution happens in this worker
process against PostgreSQL — there is no external orchestrator to reach, gate on, or reconcile
against.

Failures transition the durable queue with only run ID,
attempt, stage, fixed error code, and exception type in logs. SQL, records, credentials, and
exception messages are never logged.

`REPORTING_COMPUTATION_ENABLED=false` keeps the worker healthy but stops claims and makes reporting
reads return a stable safe 503. `REPORTING_FORCE_STALE=true` is the explicit rollback to the last
verified active snapshot when the control plane is unavailable; it never re-enters the raw-source read path. Inner SQL retries are limited to an explicit connectivity
allowlist.

Run aggregate-only exact reconciliation at a reviewed fixed cutoff:

```bash
uv run --project data python -m pipelines.business_performance.rollups \
  --start 2026-07-01T00:00:00Z --cutoff 2026-07-28T18:00:00Z
```

Any future mutable source or back-dated insert outside the trailing 72-hour window requires
dirty-bucket tracking before rollout.
