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
  gap in [README.md](README.md)).
