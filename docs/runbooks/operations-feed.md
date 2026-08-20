# Live Operations Feed & Database-Size Guard

Operational runbook for the **live operations feed** — the background worker that keeps the
portfolio-production Back Office feeling like a real, moving operations platform — and the
**database-size guard** that keeps Supabase Free bounded.

> **Honesty note.** This portfolio-production environment runs **synthetic-but-canonical**
> operations data: the feed writes *real* inventory movements through the real domain rules, so
> the exact telemetry metrics (dispatch/receiving/loss) reconcile to the ledger. It is not a
> separate "demo" dataset and there is no manual "simulate" button. Business data here is
> explicitly **disposable** under the Supabase Free disposable-data waiver
> ([supabase-migrations.md](supabase-migrations.md)) and may be reset automatically to stay
> under quota.

## What this covers

- `services/central-api/scripts/operations_feed.py` — long-running writer (default ~15s tick).
- `services/central-api/scripts/db_size_guard.py` — scheduled size check + graduated action.
- `operations_feed_control` — a single-row runtime kill switch (migration `20260713_0005`).
- Telemetry enablement for production (`TELEMETRY_ENABLED=true`, 7-day retention).

## Architecture & safety properties

- **Single writer:** the feed holds a process-lifetime PostgreSQL advisory lock
  (`pg_try_advisory_lock`, key `operations_feed_lock_key`). A second instance (rolling-redeploy
  overlap, accidental scale-out) fails to acquire it and exits — no double writes.
- **Runtime kill switch:** every tick reads `operations_feed_control.enabled`. Flip it to pause
  writes **without a redeploy**; the guard flips it during a hard-limit reset.
- **Stock never negative:** movements go through `InventoryService` with the same balance checks
  as the API; deliberate occasional over-requests are genuinely rejected and emit real
  `inventory.dispatch.rejected` telemetry (no fabricated data). No security events are fabricated.
- **Off the request path:** the feed is a separate container; it never runs inside the API.

## Prerequisites / access

- Central API image (the feed reuses it), a reachable `DATABASE_URL`, and a service-account UUID
  (`OPERATIONS_FEED_USER_UUID`, or falls back to `SEED_USER_UUID`).
- Migrations at head (includes `20260713_0005_operations_feed_control`).

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `OPERATIONS_FEED_ENABLED` | `false` | Deploy-time on/off for the feed process |
| `OPERATIONS_FEED_INTERVAL_SECONDS` | `15` | Tick interval (jittered ±20%) |
| `OPERATIONS_FEED_BATCH_MIN` / `_MAX` | `1` / `4` | Movements attempted per tick |
| `OPERATIONS_FEED_BACKFILL_DAYS` | `10` | Rolling history seeded on first start / after reset |
| `OPERATIONS_FEED_USER_UUID` | `SEED_USER_UUID` | Opaque service-account actor id |
| `TELEMETRY_ENABLED` | `true` (prod) | Enables best-effort diagnostic emission |
| `TELEMETRY_OPERATIONAL_RETENTION_DAYS` | `7` | Operational telemetry window |
| `TELEMETRY_SECURITY_RETENTION_DAYS` | `7` | Security telemetry window (portfolio deviation — see standard) |
| `DB_SIZE_SOFT_LIMIT_MB` | `400` | Prune telemetry and pause the feed at/above this |
| `DB_SIZE_HARD_LIMIT_MB` | `450` | Keep the feed paused; reset only with one-shot owner approval and a successful checkpoint |

## Kill switch (pause / resume without redeploy)

```sql
-- Pause the feed now:
UPDATE operations_feed_control SET enabled = false, note = 'manual pause', updated_at = now() WHERE id = 1;
-- Resume:
UPDATE operations_feed_control SET enabled = true,  note = 'manual resume', updated_at = now() WHERE id = 1;
```

The feed logs `operations_feed_paused` while disabled and resumes on the next tick after re-enable.
`OPERATIONS_FEED_ENABLED=false` (redeploy) is the deploy-time hard stop.

## Declarative maintenance worker

`compose.coolify.yaml` deploys one always-on `maintenance-worker`; no Coolify cron is required.
It runs the database-size guard every 15 minutes and prunes telemetry plus business events daily
at 02:15 America/Chicago. The container is read-only with only `/tmp` writable, uses the runtime
database role, and restarts on failure. Remove any legacy Coolify scheduled tasks before rollout
to prevent duplicate execution.

### Size-guard behaviour

- **< 400 MB:** logs `db_size_measured` only.
- **≥ 400 MB (soft):** prunes telemetry, pauses the feed, and logs
  `db_size_soft_limit_reached` (WARNING). It does not reset or auto-resume.
- **≥ 450 MB (hard):** keeps the feed paused and logs `db_size_hard_limit_reached` (ERROR).
  Destructive reset is refused unless the owner writes the exact one-shot note
  `owner-approved-db-size-reset` while the feed remains disabled. The note is consumed before work
  begins. The guard then enqueues and observes a normal-worker checkpoint; only success permits the
  ledger reset/reseed and automatic re-enable. Any failed, stale, missing, or unconfirmed checkpoint
  leaves the ledger intact and the feed paused.

The July 28 read-only production rescan measured roughly 5.7% growth over the comparison window;
retain the 15-minute guard cadence and remeasure before changing either threshold.

### Growth trajectory against the reset threshold (spec.md §7.4 item 5)

Measured from the Supabase snapshot of 2026-08-20, at the 15 s feed interval, **with no ledger rows
deleted** — the movement ledger is deliberately never pruned (`spec.md` line 696), so the guard
thresholds, not retention, are what bound it.

| Object | Size | Share |
|---|---|---|
| `public.stock_exits` | 119.29 MB | 43.1% |
| `public.stock_entries` | 106.23 MB | 38.4% |
| `ix_stock_exits_*` | 19.64 MB | 7.1% |
| `ix_stock_entries_*` | 17.35 MB | 6.3% |
| `reporting.hourly_activity_rollups` | 15.41 MB | 5.6% |
| **Total database** (`pg_database_size`) | **272.3 MB** | what the guard measures against 400/450 MB |

Disk usage is a different, larger number: 525.59 MB of a 1.9 GB volume (~27%), because the volume
also carries WAL (~80 MB) and system files (~169 MB). The guard reads `pg_database_size` only, so
compare it against the 272.3 MB row above — not against disk usage.

The ledger and its indexes are ~95% of the database. At a 15 s tick and a 1–4 movement batch
(~2.5 average) the feed writes on the order of 14,000 movements/day; against the measured ~185 B
per ledger row plus index, that is roughly **3 MB/day**.

**That puts the 400 MB soft limit approximately six weeks out from the 2026-08-20 snapshot.**
Reaching it does not lose data and does not fill the disk — the guard prunes telemetry and
**pauses the live feed**, and it does not auto-resume. The dashboards go static until an operator
acts. Treat the soft limit as a scheduled demo outage, not a storage emergency.

Levers, cheapest first:

1. **Raise `OPERATIONS_FEED_INTERVAL_SECONDS`** (Coolify env + restart, no redeploy, no code). 30 s
   roughly doubles the runway and 60 s roughly quadruples it, at proportionally lower write IO.
2. **Raise `DB_SIZE_SOFT_LIMIT_MB` / `DB_SIZE_HARD_LIMIT_MB`.** There is real headroom — 450 MB is
   22% of the 2 GB volume — but re-measure before moving them, and keep the soft/hard gap.
3. **Owner-approved ledger reset.** The documented destructive path: pause the feed, write the
   `owner-approved-db-size-reset` note, and let the guard checkpoint, truncate, reseed, and resume.

Note that disk space and disk **IO** are separate budgets. The August 2026 Supabase alert was IO
budget exhaustion at 26% disk usage; see the covering-index and heartbeat changes in migration
`20260820_0019` and `worker.py`. Slowing the feed helps both; raising the size thresholds helps
only the former.

## Verification

- `python -m scripts.operations_feed` with `OPERATIONS_FEED_ENABLED=true` populates
  `GET /telemetry/metrics/*` for the default range; totals reconcile to `count`/`sum` over the
  ledger, and `current_stock` never goes negative.
- Two feed instances → only one writes (advisory lock); the other logs `operations_feed_not_leader`.
- Toggling the control row pauses/resumes writes with no redeploy.
- Forcing `database_size_mb` past the hard limit without the one-shot note leaves the ledger intact
  and the feed paused. With a fresh note, a successful checkpoint permits a consistent reset/reseed;
  a failed/stale checkpoint still blocks it. Automated coverage:
  `services/central-api/tests/test_operations_feed.py`.

## Rollback / disable

- Set `OPERATIONS_FEED_ENABLED=false` and redeploy the feed service (or scale it to 0), or flip the
  control row to `enabled=false` for an immediate, no-redeploy pause.
- To stop production telemetry collection entirely, set `TELEMETRY_ENABLED=false` on both
  `central-api` and `operations-feed` (exact metric endpoints keep working; only emission stops).

## Known gaps

- An owner-approved reset still uses a **reset/reseed** (disposable-data) strategy, not
  continuity-preserving ledger compaction; it is never an unattended quota response.
- No external alerting on the guard's WARNING/ERROR logs yet (tracked with the broader monitoring
  gap in [README.md](README.md)). The soft limit pausing the feed is therefore **silent**: the
  dashboards simply stop advancing. Until alerting exists, re-check `db_size_measured` against the
  trajectory above periodically rather than waiting to notice static dashboards.
- Nothing watches the Supabase **disk IO** budget, which is a separate quota from disk space and is
  what actually alerted in August 2026.
