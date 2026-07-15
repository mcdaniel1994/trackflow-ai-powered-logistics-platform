# Brief: Data Pipelines & Telemetry

## Client: TrackFlow · Stakeholder: Andrés Kim (CTO)

## Status

In progress — dedicated Prefect production remediation Phases 1-2 are implemented and locally
verified. A private digest-pinned Prefect 3.7.8 Server now uses a dedicated PostgreSQL 16 database;
reporting and maintenance clients target it while `reporting.pipeline_runs` remains the sole
dispatch authority. Continuous claim renewal, token-guarded Prefect correlation, stage progress,
orchestrator health, orphan reconciliation, and a hard run watchdog are implemented through
Alembic revision `20260716_0010`. Optional recovery-state persistence/backups, operator UX, and
external soak/restore acceptance gates remain. The earlier
telemetry slice, live operations feed, durable weekly business-performance pipeline, Back Office
reporting surface, declarative reporting/maintenance workers, production migration verifier,
readiness probes, and automatic image rollback are implemented and locally verified through
Alembic revision `20260716_0010`. Coolify no longer needs separate cron configuration. Before the
hardened workflow is enabled, rotate the previously exposed migration credential, grant the
migration role database-level `CREATE`, and store the replacement once as the GitHub Production
environment secret `MIGRATION_DATABASE_URL`. KPI consumers are Thomas Harry (CEO) and Ana
Whitfield (Head of Warehouse Operations).

The engagement delivers a **Phase 1 slice only**: exact warehouse metrics read from the
existing inventory tables, best-effort operational/security diagnostics, and a Back Office
dashboard. It is not a full observability platform — metrics/tracing backends, correlation
IDs, browser analytics, durable event queues, and AI telemetry are explicitly deferred.

**Update (live operations feed):** to make the portfolio-production Back Office feel like a
real operations platform, a follow-on slice enables production telemetry collection
(`TELEMETRY_ENABLED=true`, 7-day retention with a scheduled prune) and adds a **live operations
feed** worker (`scripts/operations_feed.py`) that writes real, **synthetic-but-canonical**
inventory movements ~every 5s — so the exact metrics stay live and reconcilable — guarded by a
single-writer advisory lock, an `operations_feed_control` runtime kill switch, and a
`scripts/db_size_guard.py` size guard (400/450 MB, ledger-safe reset) that keeps Supabase Free
bounded. Dashboards auto-refresh ~5s without flicker and a live **Operations Overview** replaces
the static "Inventory + Carriers" landing. No security events are fabricated; real carriers
tables remain a future engagement. See `docs/runbooks/operations-feed.md`.

## Background

TrackFlow runs warehouses in Los Angeles and Zaragoza. Engagement 5 delivered the Central
API inventory system: SKUs, immutable `StockEntry` receipts, and `StockExit` dispatches or
losses, with stock always computed and never edited directly. That system faithfully records
what happened, but it cannot yet answer the operational questions leadership keeps asking:
how much are we dispatching per warehouse, how often do dispatch attempts fail and why, how
much stock is written off as loss, and whether our protected APIs are being probed.

Today the platform has structured service logs, `/health` probes, and tests proving secrets
are never logged — but no telemetry store, no metrics, no reporting surface. Engagement 6 adds
the first honest, valuable telemetry slice without overstating what exists.

## Stakeholder Request

Andrés Kim, CTO, framed the engagement:

> Thomas and Ana keep asking me questions our dashboards can't answer, and I won't ship a
> number I can't stand behind. Give me warehouse-segmented telemetry that's actually
> trustworthy. Dispatch volume, receiving volume, and stock loss must be exact — they come
> from the real inventory tables, split by LA and ZGZ, never mixed. Rejected dispatches and
> API access denials are useful diagnostics, but don't dress up best-effort data as an exact
> KPI, and don't put telemetry on the critical path of an inventory write. No customer PII,
> no client brand names, no operative emails — opaque identifiers only. Login auditing stays
> in Identity's logs for now; Identity has no warehouse, so don't invent one. Make it readable
> from the Back Office, using the same navigation pattern as Inventory Management.

## Assignment

Add a `telemetry` domain to the Central API modular monolith and a read-only Telemetry route
to the Back Office. Compute exact metrics directly from `StockEntry`/`StockExit`. Capture
rejected dispatches and API access-denials as **best-effort diagnostics** emitted *after* the
HTTP response, stored in a new `telemetry_events` PostgreSQL table with allowlisted, PII-free
fields and enforced retention. Keep login auditing in Identity as safe, secret-free log lines.
Surface everything through bounded, aggregates-only reporting endpoints and a Fulfilment /
Security dashboard, reusing the existing inventory navigation pattern.

## What You're Building

### Delivery guarantee (the central design decision)

Phase 1 deliberately does not claim exact KPIs, zero lost events, zero request-path effect, and
no durable delivery infrastructure all at once. Instead:

- **Exact metrics** (dispatch volume, receiving volume, stock-loss count/units) are read with
  read-only SQL `GROUP BY` over `StockExit`/`StockEntry`. They are durable and reconcilable and
  require no telemetry events.
- **Rejected dispatches and API access-denials** are best-effort diagnostics emitted through a
  post-response background task — no synchronous telemetry round trip on the business request
  path — and may be lost on a crash/restart. They are never used as an exact KPI denominator.
- The dispatch failure ratio is presented as a **labeled diagnostic**, alongside exact dispatch
  volume, never as an exact metric.

### Central API `telemetry` domain

- New domain `services/central-api/central_api/domains/telemetry/`
  (`models/repository/schemas/service/router.py`) and Alembic migration
  `20260709_0004_telemetry_events.py`.
- Table `telemetry_events`: `id`, `event`, `category` (`operational`|`security`),
  `occurred_at` (timestamptz UTC), `service`, `env`, `severity`, `warehouse` (nullable
  `LA`/`ZGZ`), `reason_code` (nullable), `value` (nullable int for quantity), `properties`
  (JSONB, allowlisted). Indexed on `(event, occurred_at)` and `(event, warehouse, occurred_at)`.
- Property allowlists (unknown keys rejected before insert):
  - `inventory.dispatch.rejected`: `{warehouse, reason_code, quantity?}`,
    `reason_code ∈ {INSUFFICIENT_STOCK, SKU_NOT_FOUND, WAREHOUSE_MISMATCH}`.
  - `api.access.denied`: `{reason}`, `reason ∈ {unauthenticated, csrf, password_change_required}`.
- Never stored: emails, names, recipient data, tokens, secrets, free text, `client_id`,
  request paths.

### Emission (best-effort, off the request path)

- Emit rejected-dispatch and access-denied events via a Starlette `BackgroundTask` attached to
  the outgoing error response, inserting one row in its own short-lived session, wrapped so any
  failure is logged at `WARNING` and swallowed. A telemetry failure can never fail or slow a
  business operation.
- Extend `InventoryError` with a safe `reason_code` and the attempted `warehouse`/`exit_type`
  so the rejection event can be assembled without inspecting payloads again.
- `TELEMETRY_ENABLED=false` disables all emission (fail-open to normal operation).

### Reporting endpoints (bounded, aggregates-only, `current_principal`)

Required `from`/`to` (`YYYY-MM-DD`), validated (`from <= to`, range `<= 92` days → `400`);
UTC calendar-day grouping; null-`warehouse` rows excluded from segmented metrics; empty range →
`200` with echoed period and `rows: []`. No endpoint returns raw event rows.

- `GET /telemetry/metrics/dispatch` → `{period, rows:[{date, warehouse, dispatched, rejected, indicative_failure_rate}]}`
  (`dispatched` exact; `rejected` best-effort; ratio labeled diagnostic).
- `GET /telemetry/metrics/receiving` → `{period, rows:[{date, warehouse, count}]}` (exact).
- `GET /telemetry/metrics/stock-loss` → `{period, rows:[{date, warehouse, count, units}]}` (exact).
- `GET /telemetry/metrics/access-denials` → `{period, rows:[{date, reason, count}]}` (best-effort; no warehouse).

### Identity auth audit (logs only in Phase 1)

Structured, secret-free `auth.login.succeeded` / `auth.login.failed` (safe `reason`) /
`auth.session.expired` log lines in `services/identity/`, covered by `caplog` tests asserting no
email, password, token, or warehouse leaks. Not surfaced as a dashboard KPI in Phase 1.

### Back Office Telemetry route

- Route `app/(protected)/backoffice/telemetry/` (default redirects to `fulfilment`), with
  `fulfilment/` and `security/` subviews.
- Reuse the two existing navigation patterns: add a single **Telemetry** item to
  `BackofficeNavigation.tsx` (`icon` a Lucide component reference, not JSX), and add a
  `TelemetryPageHeader.tsx` segmented sub-nav cloned from `InventoryPageHeader.tsx`.
- Read-only BFF `app/api/telemetry/[[...path]]/route.ts` allowlisting only the four `GET metrics/*`
  paths → `proxyRequest(centralAPIURL())`; typed fetchers/types in `lib/telemetry/`.
- Visualization uses existing `StatCard` + accessible tables (no new charting dependency in
  Phase 1). Best-effort figures are badged "diagnostic". Loading / empty / error states follow the
  inventory/incidents view conventions.

### Retention

`services/central-api/scripts/prune_telemetry_events.py` prunes `operational` rows after 90 days
and `security` rows after 365 days (env-configurable). It must be wired to a scheduled runner
before `TELEMETRY_ENABLED=true` in production; if scheduling is not ready at cutover, a
time-bounded exception (owner: Andrés Kim; deadline: 30 days after enablement) is recorded in
`docs/runbooks/telemetry-inventory.md`.

## Acceptance Criteria

- Dispatch/receiving/stock-loss metrics are exact, warehouse-segmented (`LA`/`ZGZ`, never mixed),
  and reconcile to `StockEntry`/`StockExit` rows.
- Rejected-dispatch and access-denied events are best-effort, allowlisted, PII-free, and clearly
  labeled diagnostic in the UI; no exact KPI is built on them.
- No synchronous telemetry round trip is added to the inventory/auth request path; a forced
  emitter failure leaves the business operation unaffected.
- A rejected dispatch and a CSRF-denied protected request each produce exactly one correctly
  categorized `telemetry_events` row; a failed login produces an Identity audit log line (no
  email/password/token) and **no** `telemetry_events` row.
- `api.access.denied` reasons are limited to `unauthenticated`/`csrf`/`password_change_required`,
  with no change to the shared auth verifier and no weakening of its non-enumerating responses.
- Reporting endpoints validate `from`/`to`, enforce the max range, exclude null warehouses,
  return aggregates only, and require an authenticated Back Office session.
- Alembic `0004` upgrades an empty disposable PostgreSQL database and its rollback is verified.
- `telemetry_events` retention is enforced by the prune command wired to a scheduler, or a filed
  time-bounded exception exists with owner and deadline.
- The Telemetry route is reachable from the sidebar, renders Fulfilment and Security views with
  correct segmented data and states, and exposes no raw event rows or PII.
- `docs/runbooks/telemetry-inventory.md`, `docs/standards/telemetry-standard.md` §10, and the
  engagement-tracking docs reflect only what shipped.
- Ruff, mypy, package build, pytest with coverage (Central API + Identity), and the Back Office
  type-check/lint/build/tests pass locally.

## Out of Scope

- Browser-emitted product-analytics or navigation telemetry, a client `track()` helper, and any
  telemetry ingest `POST` endpoint (deferred to Phase 2).
- A durable outbox/queue and an exact dispatch failure-rate KPI (deferred).
- A dashboard login/auth KPI, finer token-failure reasons, and any change to `packages/trackflow_auth`.
- Warehouse segmentation of auth events (Identity has no warehouse claim).
- Correlation-ID propagation, a metrics/tracing backend, external uptime/alerting, and AI telemetry.
- Changes to delivered Engagement 2 behavior in `packages/shared/`, or to Identity's TinyDB ownership.
- Running migrations, seeds, or enabling production telemetry collection against Supabase without
  the required confirmation, retention wiring, and approval.
