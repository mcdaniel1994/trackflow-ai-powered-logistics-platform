# Design: Movement Ledger Retention

**Status:** Proposed — awaiting owner approval
**Required by:** `docs/planning/remaining_planning/spec.md` §8.4
**Implements:** `services/central-api/scripts/prune_movement_ledger.py`
**Date:** 2026-08-20

## Why this document exists

`spec.md` §8.4 states that `stock_entries` and `stock_exits` are immutable, and that
**"any future scheme that removes movement rows must first prove, in its own approved design,
that computed stock and audit correctness are preserved — because stock is computed from the
full movement history, and removing movements silently changes computed stock."**

This is that design. It is the approval gate, not a summary of one.

## Objective

Run indefinitely on the Supabase Free tier with no operator intervention, by giving the database
a hard storage ceiling instead of a growth curve that eventually trips `db_size_guard`'s 400 MB
soft limit and silently pauses the live operations feed.

## The §8.4 proof

### Computed stock is preserved

The premise of §8.4 — "stock is computed from the full movement history" — **is no longer true**,
and that is what makes retention safe. Migration `20260820_0020` materialized stock into
`stock_balances`:

- The migration seeded it with one set-based aggregation over the entire ledger, so the stored
  value is exactly what the old `current_stock` computed.
- Every subsequent movement updates it in the same transaction, under the `SELECT ... FOR UPDATE`
  lock on the parent SKU that `record_outbound` already took. A concurrent-dispatch race test
  asserts zero drift after two threads contend for the same stock.
- Bulk paths (seed, feed backfill, guard reset) re-derive the whole table with the same
  aggregation rather than threading deltas through loops.

Because the balance is carried forward incrementally, **deleting old movements does not change
it.** The invariant that must hold is not "the ledger is complete" but "the balance equals the
ledger's effect since the beginning of time", and the balance carries that history in a single row.

`scripts/verify_stock_balances.py` re-derives every balance from the ledger read-only and exits
non-zero on any disagreement. Run before and after the first prune, it is the evidence. **Note it
can only prove agreement over the retained window once pruning has run** — which is why it must be
run and recorded *before* the first prune, while the full ledger is still present.

### Audit correctness is *not* fully preserved — stated plainly

This is a real loss, and the spec asks for it to be proven, not hidden:

- The Back Office movement timeline (`list_movements`) will show only the retained window.
- Reporting rollups cannot be recomputed for any period older than the window. Already-published
  weekly facts in `reporting.weekly_warehouse_client_performance` are durable and unaffected;
  what is lost is the ability to *re-derive* them.
- Per-movement audit attribution (`user_uuid`, references, tracking numbers) is destroyed for
  pruned rows and is not recoverable.

The accepted trade is: TrackFlow is a portfolio deployment on a free tier where unbounded growth
ends in a silent feed pause. Bounded storage is worth more than unbounded per-movement audit
history. **An installation with genuine audit obligations must not enable this job** — set
`MOVEMENT_RETENTION_DAYS` high enough to be inert, or remove the job.

## The window: 30 days

| Constraint | Value | Consequence of violating it |
|---|---|---|
| Reporting recompute window (`DEFAULT_RECOMPUTE_WEEKS = 3`) | 21 days | Weeks inside the window recompute against a partial ledger and **republish lower numbers with no error** |
| Enforced floor (`MINIMUM_MOVEMENT_RETENTION_DAYS`) | 25 days | Job refuses to run below this |
| Chosen window (`MOVEMENT_RETENTION_DAYS`) | **30 days** | 9 days of margin over the recompute window |
| Feed backfill (`OPERATIONS_FEED_BACKFILL_DAYS`) | 10 days | Comfortably inside the window |

A 14-day window — proposed during discussion — is rejected: it deletes inside the 21-day recompute
range and corrupts the weekly report.

## Foreign keys decide the order

`inventory_discrepancies.stock_exit_id` and `stockout_events.stock_exit_id` are both
`ON DELETE RESTRICT` into `stock_exits`. Two consequences:

1. **Children must be deleted before parents**, or the parent DELETE raises.
2. **The two windows cannot differ.** Business events previously had a 26-week window while the
   ledger had none. A 30-day ledger window with 26-week children makes the parent delete fail for
   up to 182 days. The separate `prune_business_events` job was therefore removed and folded into
   this one, under a single cutoff — two jobs with two cutoffs on FK-linked tables is how the
   windows drift apart and the delete starts failing at 02:15 with no one watching.

**Children are selected by their parent's age, not their own timestamp.** A discrepancy can be
recorded days after the dispatch it describes, so a child inside the window can reference a parent
outside it. Filtering children on `detected_at` would leave exactly those rows behind and fail the
parent delete. The job filters on the parent's `created_at` throughout.

Order: `inventory_discrepancies` → `stockout_events` → `stock_exits` → `stock_entries`.

## Execution safety

- **Micro-batches.** `DELETE ... WHERE id IN (SELECT id ... ORDER BY id LIMIT 1000)`, one
  transaction per batch, `0.5 s` between batches. Autovacuum reclaims continuously instead of
  facing one large transaction. The predicate is sargable — `created_at < :cutoff`, no casts or
  functions wrapping the indexed column — and served by `ix_stock_*_created_at`.
- **Time budget.** 30 minutes per run. The first run has ~70 days of backlog (~1.2 M rows); it
  stops at the budget and resumes the next night. The job is idempotent.
- **Stops at a step boundary.** If the budget expires mid-step it does not proceed to parents whose
  children are still present, so a partial run is always resumable rather than leaving an
  impossible delete.
- **Fails closed** on a window below the floor.

## What this does and does not do to disk usage

**It does not shrink the database.** `DELETE` does not return space to the operating system, and
because the oldest rows are deleted first, the freed pages sit at the front of the heap where plain
`VACUUM` cannot truncate them.

What it buys is a **plateau**: new movements reuse the freed pages, so the ledger stops growing.
Expected steady state is near the current 272 MB — comfortably under the 400 MB soft limit, and
stable indefinitely. That satisfies the objective.

To actually reclaim the ~160 MB of freed space, a one-off `VACUUM FULL` (ACCESS EXCLUSIVE lock,
needs ~2× the table size free) or `pg_repack` is required. That is a deliberate operator action,
not part of this job, and is not needed to hold the ceiling.

## Rollout

1. Record `scripts.verify_stock_balances` output **before** the first prune — the correctness
   evidence, only obtainable while the full ledger exists.
2. Deploy with `MOVEMENT_RETENTION_DAYS` unset (defaults to 30).
3. Watch the first few 02:15 runs for `movement_ledger_prune_complete` and
   `movement_ledger_prune_incomplete`; expect several nights of `incomplete` while the backlog
   clears.
4. Confirm `db_size_measured` plateaus rather than continuing to climb.
5. Re-run `verify_stock_balances`; it must still report zero drift.

## Reversibility

Not reversible. Deleted movements are unrecoverable — Supabase Free has no scheduled backups under
the accepted disposable-data waiver. Setting `MOVEMENT_RETENTION_DAYS` very high stops further
deletion but restores nothing.
