# Engagement 6.1 Mandatory Production Rescan — 2026-07-28

**Environment:** portfolio production, Supabase PostgreSQL through the configured inspection role
**Access mode:** read-only inspection; no production mutation performed
**Purpose:** specification §1.3 pre-implementation gate

No credential, DSN, connection string, raw business row, client identifier, or customer value is
recorded here.

## Access-boundary verification

| Check | Result |
|---|---|
| Current role | `trackflow_inspector` |
| Transaction read-only | `on` |
| Default transaction read-only | `on` |
| Superuser | false |
| Create database | false |
| Create role | false |

The client also forced `default_transaction_read_only=on`, opened an explicit read-only
transaction, stopped on the first SQL error, and applied a 60-second statement timeout.

## Production snapshot

| Measure | 2026-07-27 specification baseline | 2026-07-28 rescan |
|---|---:|---:|
| PostgreSQL | 17.6 | 17.6 |
| Alembic revision | `20260716_0010` | `20260716_0010` |
| Database size | 94 MB | 98 MB |
| `stock_entries` | 195,638 | 206,727 |
| `stock_exits` | 221,731 | 234,339 |
| Dispatch exits | 200,318 | 211,654 |
| Loss exits | 21,413 | 22,685 |
| `inventory_discrepancies` | 3,708 | 3,931 |
| `stockout_events` | 0 | 0 |
| `telemetry_events` | 9,025 | 8,465 |
| `inventory.dispatch.rejected` | 8,993 | 8,437 |
| `api.access.denied` | 32 | 28 |
| LA entries | 97,794 | 103,336 |
| ZGZ entries | 97,844 | 103,391 |
| Published weekly rows | 0 | 0 |
| Pipeline runs | 16 failed | 17 failed |
| Maximum connections | 60 | 60 |
| Connections observed in use | 24 | 24 |

All 17 pipeline runs remain terminal `MAX_ATTEMPTS_EXCEEDED`: twelve retain `transform` as their
current stage, one retains `extract`, and four have no current stage. All three row-count fields
remain null on every run. The reporting worker heartbeat and progress timestamp were current at
inspection time and `orchestrator_healthy` was true.

Daily aggregate movement volumes continue to show the July 21–22 outage and returned to roughly
35,000 movements per complete day from July 23 onward. The current partial day was not treated as a
rate change.

Installed extensions remain `pg_stat_statements`, `pgcrypto`, `plpgsql`, `supabase_vault`, and
`uuid-ossp`.

## Read-only query measurements

All plans were captured with `EXPLAIN (ANALYZE, BUFFERS)` inside the read-only transaction.

| Query | Rows scanned | Aggregate rows | Execution |
|---|---:|---:|---:|
| Full-history hourly entry rollup | 206,727 | 1,803 | 183.9 ms |
| Full-history hourly exit rollup, split by exit type | 234,339 | 3,592 | 226.0 ms |
| Current full-history exit extract shape | 234,339 | 234,339 | 548.3 ms |

The two rollups total approximately 410 ms, consistent with the specification baseline. The plans
used sequential scans of the movement tables, small joins to the six-row SKU table, and in-memory
hash aggregates without spill.

## Gate decision

- Entry growth: +5.7%, below the >25% stop threshold.
- Exit growth: +5.7%, below the >25% stop threshold.
- Alembic revision: unchanged.
- Full-history and individual statements: well below specification §7 budgets.
- Inspection role: read-only and non-privileged.

**Decision:** the mandatory rescan passes. Phase 6.1 implementation may proceed without revising
batch sizing or returning the specification for owner amendment.
