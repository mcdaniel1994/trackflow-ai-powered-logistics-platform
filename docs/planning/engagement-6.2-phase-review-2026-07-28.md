# Engagement 6.2 Local Review Evidence — 2026-07-28

## Status

Phase 6.2 is implemented and verified on disposable local PostgreSQL through additive Alembic
revision `20260728_0012`. It is **not deployed or production-accepted**. The off-by-default flag
keeps the deployed behavior unchanged until a separately reviewed production release enables
shadow computation. Phases 6.3–6.4 have not started.

Phase 6.1's remaining controlled exercises were omitted by explicit owner direction. That exception
is recorded in the Phase 6.1 production evidence and is not treated as passing evidence here.

## Delivered

- `reporting.hourly_activity_rollups` stores completed UTC hours keyed by canonical `LA`/`ZGZ`,
  source-compatible `client_id`, and `bucket_start`. Dispatch and loss counts/units are separate;
  discrepancy rate is derived and is not stored.
- `reporting.rollup_state` owns the singleton committed cutoff/publication/reconciliation state.
- The aggregation query scans entries, exits, stockouts, and discrepancies independently and joins
  only their aggregates onto a dense hour × warehouse/client grid. It never joins raw entry rows to
  raw exit rows.
- Each run captures one completed-hour UTC cutoff. Default runs recompute every hour since the last
  committed cutoff plus an unconditional trailing 72 hours. A requested ISO week remains exactly
  recomputable.
- Publication upserts the unique key, verifies the queue claim in the publishing transaction, and
  advances the cursor only in that same committed transaction.
- The reporting connection raises only its local statement timeout to 60 seconds. Central API
  retains its 15-second default.
- `REPORTING_HOURLY_ROLLUPS_ENABLED` defaults to `false` in code and both Compose definitions.
  When false, the existing daily legacy path and public API bytes remain unchanged. When true,
  Prefect executes the hourly shadow path and the internal dispatcher uses 07:00/19:00
  America/Chicago cadence slots.
- A prior image remains compatible with the additive schema: the legacy daily schedule identity
  and tables remain intact, while the new evening slot uses an additive `scheduled_for` identity.
- Successful attempt rows now persist the immutable cutoff, exact source rows scanned, and rollup
  rows written.
- `python -m pipelines.business_performance.rollups --start ... --cutoff ...` is a first-class,
  rerunnable exact raw-SQL reconciliation job. Its console output is aggregate-only.

Dirty-bucket tracking remains deliberately deferred. It becomes required if any source becomes
mutable or permits back-dated insertion outside the unconditional trailing 72-hour window.

## Reference, migration, and execution evidence

The deterministic fixtures cover:

- UTC hour boundaries and an ISO week crossing the calendar-year boundary;
- dispatch/loss separation;
- dense zero-activity dimensions and zero discrepancy denominators;
- fixed-cutoff exclusion of a mid-run back-dated insert;
- exact mismatch detection followed by trailing-window repair;
- idempotent publication with identical keys;
- feature-flag default-off behavior;
- Prefect execution of shadow rollups without writing the existing weekly table;
- twice-daily cadence identity plus legacy daily compatibility;
- attempt cutoff/scanned/written evidence;
- schema checks, foreign keys, uniqueness, indexes, upgrade, downgrade, and singleton rows.

Targeted results:

| Gate | Result |
|---|---:|
| Full data-pipeline suite | 126 passed, 1 opt-in performance test skipped; 90.18% coverage |
| Full Central API suite | 174 passed; 91.69% coverage |
| Opt-in production-volume performance test | 1 passed |
| Release-helper safety suite | 11 passed |
| Data/Central API Ruff, strict mypy, Alembic drift, builds, Compose validation | Passed |

## Performance evidence

The opt-in gate loaded **2,120,000** deterministic source/event rows, which exceeds twice the
observed production movement volume and represents the approved post-change projection test. It
cleaned the disposable database afterward.

| Measurement | Result | Budget |
|---|---:|---:|
| Full-history aggregate statement | 1.045 s | ≤ 30 s |
| Full-history aggregate + publication | 1.291 s | ≤ 60 s |
| Regular trailing-72-hour aggregate | 0.032 s | ≤ 60 s |
| Exact full-history reconciliation | 0.619 s | ≤ 60 s |
| Rollup-derived report read | 0.004 s | ≤ 2 s |
| Process peak RSS | 65,978,368 bytes | ≤ 80% of 768 MiB |
| Hourly rows published | 8,688 | informational |

All measured local budgets pass with substantial margin. These measurements do not replace live
shadow reconciliation.

## Production acceptance still required

Before Phase 6.2 can be called production-accepted:

1. review and deploy the additive `20260728_0012` migration and immutable image;
2. verify runtime grants/readiness for both new reporting tables;
3. explicitly enable the shadow flag only for the reporting worker;
4. let Prefect publish hourly shadow rollups at a fixed live cutoff;
5. run exact live reconciliation and record aggregate-only evidence;
6. confirm public reporting responses remain byte-compatible and the weekly table remains
   unchanged; and
7. rerun the same complete release gates against the immutable release candidate.

Phase 6.3 cutover must not deploy before this evidence is complete.
