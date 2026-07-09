# Telemetry Inventory

A living, security/stakeholder/operations reference for every telemetry signal TrackFlow
emits or plans to emit. It distinguishes **implemented today** from **planned (Engagement 6
Phase 1)** from **deferred/future**, and never claims a planned signal is live.

- **Authority:** collection shape and safety follow [`../standards/telemetry-standard.md`](../standards/telemetry-standard.md);
  runtime logging follows [`../standards/observability.md`](../standards/observability.md).
- **Related:** engagement scope in [`../briefs/06-data-pipelines-telemetry.md`](../briefs/06-data-pipelines-telemetry.md);
  storage/retention operations in this `docs/runbooks/` set.
- **Never** record secrets, tokens, raw PII, request bodies, or example production values in this file.

> **Maintenance rule.** Update this inventory in the **same change** whenever telemetry is
> added, changed, or removed, or whenever a signal's fields, storage, retention, access, or
> dashboard surface changes. A telemetry change is not complete until this file and the relevant
> tests/runbooks reflect it. Reviewers should reject telemetry changes that do not update this file.

Status legend: ✅ Implemented today · 🧭 Engagement 6 Phase 1 — implemented in code and verified
locally; **production collection is gated** on a scheduled retention prune before
`TELEMETRY_ENABLED=true` · ⏳ Deferred/future.

---

## 1. Implemented today (✅)

These exist in the repository now and are evidenced by tests or verified deployment.

| Signal | Owner / component | Trigger / source | Purpose & stakeholder question | Category | Safe fields / explicit exclusions | Storage | Retention | Access | Reporting surface | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Central API service logs | `services/central-api` (`main.py`, domain services) | Handled failures, DB errors, unexpected exceptions | "Why did a request fail?" (Andrés Kim / on-call) | Application log | `operation`, `error_type`, safe messages. **Excludes** SQL, connection URLs, payload values, secrets | stdout (container) | Governed by container/host log lifecycle (no central aggregation) | Server/deploy operators | None (logs only) | `services/central-api/central_api/main.py`, domain `service.py` | ✅ |
| Identity service logs | `services/identity` | Auth lifecycle, password reset, user management | "What auth-relevant events occurred?" | Application / audit log | who/what/when/outcome. **Excludes** passwords, tokens, reset links, emails | stdout (container) | Container/host log lifecycle | Server/deploy operators | None | `test_password_reset.py`, `test_users.py` (`caplog` assert secrets absent) | ✅ |
| Health / readiness checks | Identity, Central API, Back Office | Container/orchestrator probe; `GET /health` (Central API) | "Is the service up and is its DB reachable?" | Operational signal | `status`, `database`. **Excludes** connection detail | Ephemeral (probe response) | N/A | Deploy/monitoring | Coolify container health | `central_api/main.py:health`; `runbooks/backend-coolify-deployment.md` | ✅ |

**Not implemented today (intentional gaps — do not claim otherwise):** centralized/structured log aggregation & retention, metrics, distributed tracing, request-correlation IDs, product analytics, alerting/uptime monitoring, a telemetry event store, and any AI telemetry. See `../standards/observability.md` §4.

---

## 2. Engagement 6 Phase 1 (🧭 — implemented in code, verified locally; production collection gated)

Implemented in `services/central-api/central_api/domains/telemetry/`,
`services/central-api/central_api/main.py` (post-response emitters),
`services/identity/identity/service.py` (auth audit logs), and
`uis/backoffice/` (`/backoffice/telemetry` route + read-only BFF). Test evidence:
`services/central-api/tests/test_telemetry.py`, `services/identity/tests/test_auth_audit.py`,
`uis/backoffice/tests/telemetry-bff.test.ts`, and `uis/backoffice/tests/telemetry-ui.test.tsx`.
**Production collection is disabled (`TELEMETRY_ENABLED=false`) until the retention prune is wired
to a scheduler** (see 2.4). Server-owned only; **no browser telemetry** in Phase 1. Delivery guarantee: exact metrics are read
from the durable business tables (`StockEntry`/`StockExit`); rejection/denial events are **best-effort
diagnostics** emitted **after** the HTTP response (no synchronous telemetry round trip on the business
path) and **may be lost on crash/restart**. No exact KPI is built on best-effort telemetry.

### 2.1 Exact metrics — derived from the business system of record (no events stored)

| Metric | Owner / source | Purpose & stakeholder question | Category | Safe fields / exclusions | Storage | Retention | Access | Reporting surface | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| Dispatch volume /day/warehouse | Central API telemetry domain; reads `StockExit` (`exit_type=dispatch`) | "How much are we shipping per warehouse?" (Thomas Harry, Ana Whitfield) | Operational metric (exact) | `date`, `warehouse (LA/ZGZ)`, `count`. Excludes recipient data, `client_id` (not in schema) | Business tables (durable) | Business-record lifetime | All authenticated Back Office users | Telemetry → Fulfilment | Plan B2/B6 (this engagement) | 🧭 |
| Receiving volume /day/warehouse | reads `StockEntry` | "Inbound throughput per warehouse?" | Operational metric (exact) | `date`, `warehouse`, `count` | Business tables | Business-record lifetime | Authenticated users | Fulfilment | Plan B2/B6 | 🧭 |
| Stock-loss count + units /day/warehouse | reads `StockExit` (`exit_type=loss`) | "Where is stock lost (shrinkage)?" (Ana Whitfield) | Operational/integrity metric (exact) | `date`, `warehouse`, `count`, `units` | Business tables | Business-record lifetime | Authenticated users | Telemetry → Security | Plan B2/B6 | 🧭 |

### 2.2 Best-effort diagnostics — stored in `telemetry_events`

| Signal | Owner / trigger | Purpose & stakeholder question | Category | Safe fields (allowlist) / exclusions | Storage | Retention | Access | Reporting surface | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `inventory.dispatch.rejected` | Central API inventory error path; post-response `BackgroundTask` | "How often, and why, do dispatch attempts fail per warehouse?" (Ana Whitfield) — diagnostic, best-effort | Operational (diagnostic) | Allowlist `{warehouse, reason_code, quantity?}`; `reason_code` ∈ `INSUFFICIENT_STOCK`/`SKU_NOT_FOUND`/`WAREHOUSE_MISMATCH`. **Excludes** actor, SKU codes beyond id, tokens, free text | `telemetry_events` (PostgreSQL) | 90 days (operational) | Authenticated users (aggregates only) | Fulfilment (labeled "diagnostic — may undercount") | Plan B3/B5 | 🧭 |
| `api.access.denied` | Central API `core/dependencies.py`; post-response `BackgroundTask` | "Are protected APIs being refused / probed?" (Andrés Kim) — best-effort | Security (diagnostic) | Allowlist `{reason}`; `reason` ∈ `unauthenticated`/`csrf`/`password_change_required` **only** (the verifier normalizes all token faults to one 401 — finer reasons are **not** observable without a reviewed verifier change). **Excludes** path, token, actor, email | `telemetry_events` | 365 days (security) | Authenticated users (aggregates only) | Security | Plan B4/B5 | 🧭 |

### 2.3 Identity auth audit — logs only in Phase 1 (no `telemetry_events`, no dashboard)

| Signal | Owner / trigger | Purpose & stakeholder question | Category | Safe fields / exclusions | Storage | Retention | Access | Reporting surface | Evidence | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| `auth.login.succeeded` / `auth.login.failed` / `auth.session.expired` | `services/identity` | "What login outcomes occurred?" (security review) | Audit/security log | who/what/when/outcome, safe `reason`. **Excludes** email, password, token, **warehouse** (Identity has no warehouse claim) | Identity stdout logs | Container/host log lifecycle | Server operators | None in Phase 1 (dashboard KPI deferred) | Plan B4; `caplog` tests | 🧭 |

### 2.4 Phase 1 storage, access & retention operations

- **Store:** single table `telemetry_events` in the existing Central API (Supabase) PostgreSQL — holds **only** the best-effort diagnostics in 2.2. Exact metrics (2.1) are not duplicated into it.
- **Access control:** reporting endpoints require an authenticated Back Office session (`current_principal`) and return **aggregates only** — no endpoint exposes raw event rows; no PII is stored or returned.
- **Retention enforcement:** `services/central-api/scripts/prune_telemetry_events.py` deletes rows past each category window (operational 90d, security 365d). **Gate:** it must be wired to a scheduled runner **before `TELEMETRY_ENABLED=true` in production**. If scheduling is not ready at cutover, a time-bounded exception is recorded here — **owner: Andrés Kim (CTO); deadline: 30 days after Phase 1 production enablement** — and closed by wiring the schedule. *(No exception is active — production collection is not yet
enabled; `prune_telemetry_events` exists and is unit-tested but is not yet scheduled.)*
- **Environment separation:** every row carries `env`; non-production events must not reach the production store; tests use disposable databases.

---

## 3. Deferred / future (⏳)

Not planned for Phase 1; listed so stakeholders know the boundary. **None of these are implemented or promised by Phase 1.**

| Signal / capability | Why deferred | Would answer |
|---|---|---|
| Browser product-analytics & navigation events (`sku_list.viewed`, `dispatch_form.abandoned`, `warehouse_filter.applied`) via client `track()` + ingest `POST` BFF (`write_principal`) | Requires trusted client capture, ingest endpoint, and a shared client/server schema artifact | Product/UX behavior |
| Durable outbox/queue for rejection capture → **exact** dispatch failure-rate KPI | Phase 1 chose best-effort delivery; loss-free capture needs delivery infrastructure | Exact fulfilment failure rate |
| Dashboard login/auth KPI + finer token-failure reasons | Needs an Identity-internal aggregation path and a reviewed verifier change preserving non-enumerating responses | Login failure trends |
| Receiving→dispatch cycle-time KPI | Needs batch/lineage modeling not present today | Warehouse processing speed |
| Correlation-ID propagation, metrics backend, distributed tracing | Platform observability, larger scope | Cross-service latency/causality |
| AI telemetry (model/tool/retrieval metadata) | Belongs to Engagement 7+ AI features | AI operational behavior |
| External uptime monitoring & alerting | Ops tooling, tracked in `README.md` gaps | Availability/incident response |

---

_Update this file with every telemetry change (see the maintenance rule above)._
