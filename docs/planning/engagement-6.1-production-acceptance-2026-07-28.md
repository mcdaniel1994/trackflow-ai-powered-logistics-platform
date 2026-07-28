# Engagement 6.1 Production Acceptance Evidence — 2026-07-28

## Status

Production is running the Phase 6.1 image and additive schema. On 2026-07-28 the owner explicitly
directed the team to skip the remaining controlled production exercises and proceed to Phase 6.2.
Phase 6.1 is therefore **closed by owner exception**, not by a claim that the omitted exercises
passed. Read-only evidence is recorded below; the missing evidence remains visible in this record.

No credential, DSN, connection string, raw business row, cache nonce, customer identifier, token,
Coolify coordinate, or other secret is recorded here.

## Repository, merge, image, and deployment

| Check | Evidence |
|---|---|
| Verified `main` | `13bba2e2bdebb0c25c05ba23addbeb62bac8586b` |
| Reporting branch merge | GitHub PR #21 merged the prior Phase 6.1/6.5 branch into `main` |
| Reported PR #27 | No PR #27 exists in this repository; it must not be used as deployment evidence |
| Immutable production image | `sha-13bba2e2bdebb0c25c05ba23addbeb62bac8586b` |
| Dedicated-Prefect guard fix | Included through ancestor `fe430ab` |
| Production workflow | GitHub run `30378251370`, reusable deployment job succeeded |
| Migration | `20260716_0010 -> 20260728_0011`; runtime grants verified |
| Automatic rollback | Not invoked because deployment and core readiness passed |

The preserved deployment artifact confirmed the immutable image digest, migration result, worker
startup guard, core checks, and separate reporting verification. Inspection also found that the
archived Coolify log contained a GitHub masking directive whose argument was an opaque production
deployment coordinate. The coordinate is intentionally omitted here. The Phase 6.1 acceptance
branch removes that emission and adds a regression test proving the entry point prints only the
fixed `coolify_deployment_complete` token.

## Forced-read-only database boundary

The inspection client forced `default_transaction_read_only=on`, opened an explicit read-only
transaction, used a 60-second statement timeout, and rolled the transaction back.

| Check | Result |
|---|---|
| Current role | `trackflow_inspector` |
| Transaction read-only | `on` |
| Default transaction read-only | `on` |
| Superuser | false |
| Create database | false |
| Create role | false |
| PostgreSQL | 17.6 |
| Alembic revision | `20260728_0011` |
| Database size | 98.9 MB |
| Connections | 19 observed / 60 maximum |

## Aggregate production snapshot

| Measure | Result |
|---|---:|
| `stock_entries` | 208,581 |
| `stock_exits` | 236,437 |
| Dispatch exits | 213,553 |
| Loss exits | 22,884 |
| `inventory_discrepancies` | 3,982 |
| `stockout_events` | 0 |
| `telemetry_events` | 8,625 |
| `inventory.dispatch.rejected` | 8,596 |
| `api.access.denied` | 29 |
| LA entries | 104,251 |
| ZGZ entries | 104,330 |
| Published weekly rows | 0 |
| Pipeline runs | 20 |
| Durable attempt rows | 1 at the first snapshot |

The movement rate returned to approximately 35,000 per complete day after the July 21–22 outage.
Growth remained below the specification's 25% stop threshold.

## Read-only query measurements

| Query | Aggregate/output rows | Execution |
|---|---:|---:|
| Full-history hourly entry rollup | 1,815 | 189.5 ms |
| Full-history hourly exit rollup | 3,616 | 234.8 ms |
| Current full-history exit extract shape | 236,437 | 265.2 ms |

The measurements remain well below the specification's performance stop thresholds.

## Service and queue evidence

At the 2026-07-28 12:00 America/Chicago evidence window:

- Back Office `/api/health/live` returned `200` / `alive`.
- Back Office `/api/health/ready` returned `200` / `ready`.
- Back Office `/api/health/reporting` returned `200`, with a fresh heartbeat and a healthy
  orchestrator.
- The unauthenticated home route returned the expected `307` login redirect.
- One manual run was in `transform`, one earlier manual run was `retryable`, and one manual run
  remained requested behind them.
- The first durable attempt survived its run transition with stage `transform`, originating code
  `STALE_ABANDONED`, outcome `lease_lost`, and no exception message or build coordinate. The parent
  run retained its own queue state without erasing the attempt evidence.
- The weekly table remained empty; no weekly report has published.
- After the active legacy transform crossed its 300-second stage deadline, reporting verification
  truthfully returned `200` / `degraded` / `stuck` while liveness and core readiness both continued
  to return `200`. This is direct production evidence that a stuck report no longer fails the core
  health signals; it does not replace the required stopped-worker routing exercise.

At 12:12 America/Chicago the second originally active manual run also transitioned to `retryable`.
Its sanitized attempt row recorded `transform` / `STALE_ABANDONED` / `lease_lost` after about 976
seconds. The worker then claimed attempt 2 of the earlier retryable run while the third manual
request remained queued. This proves the durable attempt record repeats per attempt and the queue
continues under single-active-run enforcement. Final outcomes remain pending because each legacy
transform can consume roughly 16–18 minutes before lease-loss recovery and each run permits up to
five attempts.

## Repository verification completed during this pass

| Gate | Result |
|---|---|
| Phase 6.1 targeted Central API/Compose/guard tests | 46 passed |
| Release helper Ruff | Passed |
| Release safety tests | 11 passed |
| Evidence-coordinate regression | Passed |

The complete per-package release suite will be rerun after all production evidence and
documentation changes are final.

## Acceptance exercises omitted by owner direction

1. Stop only `reporting-worker` for at least 15 minutes and verify zero unrelated Back Office 5xx
   or 404 responses, core readiness, routing, and no deployment rollback.
2. Break database reachability, schema compatibility, and runtime-role validation one at a time
   and verify each release failure triggers the documented image rollback.
3. Remove one reporting-only grant and verify reporting verification fails while core readiness
   stays healthy and no rollback occurs.
4. Force extract, transform, and load failures; replace the worker container; retrieve each
   sanitized durable attempt afterward.
5. Verify the live `reporting-logs` volume, directory/file permissions and ownership, rotation,
   retention, byte ceiling, content safety, container exit evidence, and exactly one claiming
   process.
6. Verify the Coolify notification destination and deliver a test notification.
7. Observe actual Traefik routing and Coolify behavior for an unhealthy container without assuming
   the outcome.

None of these exercises was executed. The owner first approved exercise 1, then explicitly withdrew
that execution request and directed work to continue with Phase 6.2. The exception does not convert
an unobserved result into passing evidence and must not be reused as proof for a later production
gate.
