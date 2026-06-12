# TrackFlow Central API — Backend Architecture Proposal

**Audience:** Andrés Kim (CTO) and the TrackFlow Tech engineering team
**Status:** Planning proposal — no implementation
**Prepared from:** `docs/planning/backend-architecture-planning.md` + a full scan of the
existing monorepo (`memory-bank/`, `AGENTS.md`, `CLAUDE.md`, `README.md`,
`docs/briefs/`, `packages/shared/`, `uis/`, `services/`)
**Proposed home for the build:** `services/central-api/` (future Central API engagement)

---

## 1. Purpose & Scope

This document is the architecture proposal for TrackFlow's **Central API** — the
backend service that will sit behind the existing frontends and become the single
source of truth for logistics data and business logic.

**What this document is:**

- A reasoned recommendation for *how* the backend should be structured before any code
  is written.
- A reference an engineer or AI coding agent can read and then begin planning
  implementation without further verbal explanation.

**What this document is *not*:**

- It is **not** the Engagement 5 brief (those live in `docs/briefs/NN-<slug>.md`).
- It does **not** scaffold FastAPI, install dependencies, create endpoints, change the
  repository structure, or update engagement-tracking docs.
- It is separate from the Incident Report Processor subproject, which lives in
  `services/incident-processor/` and does not consume the reserved `services/central-api/`
  path.

All folder trees and route tables below are **illustrative documentation**, not code to
be generated as part of this task. The actual scaffold belongs to Engagement 5, guided
by the brief that will accompany it.

---

## 2. Architectural Pattern & Justification

### Recommendation: a domain-oriented, layered **modular monolith**

TrackFlow should build the Central API as **one deployable FastAPI service**, internally
partitioned by **business domain**, where each domain is internally **layered**:

```text
router (HTTP)  →  service (business logic)  →  repository (data access)  →  model / schema
```

- **Domain-oriented** means the top-level partition of the codebase follows TrackFlow's
  real operational areas (inventory, carriers, returns, …), not technical mechanics.
- **Layered within each domain** means every domain separates its HTTP surface from its
  business rules from its data access, so logic is testable and routes stay thin.
- **Modular monolith** means one service, one deployment, one database — but with
  internal boundaries drawn cleanly enough that any single domain could later be lifted
  into its own service if a real scaling need appears.

### Why this fits TrackFlow specifically

TrackFlow's problems are fundamentally about **fragmentation and manual work**, not
about scale:

| TrackFlow reality (`projectbrief.md`) | Architectural implication |
|---|---|
| Two warehouses (LA, Zaragoza) with no shared inventory visibility | Needs a *single* authoritative inventory domain, not two systems duplicated again |
| Eight carriers, no unified performance data | A carriers domain that aggregates on-time rate / cost-per-kg / incidents in one place |
| Returns are 18–25% of volume, reviewed by hand | A returns domain with auditable, rule-driven workflows |
| ~80% of support queries are repetitive | A support domain ready to host automation and, later, AI agents |
| No CRM — spreadsheets and email | A customers/CRM domain to replace ad-hoc tools |
| Weekly reporting assembled manually | A reports domain that reads across other domains |
| ~130 staff, 4 key stakeholders, one Tech team | Operational scale that a single well-structured service serves comfortably |
| Roadmap: data pipelines, RAG, AI agents (Eng. 6–8) | Strong reason to choose Python; clean AI/automation seams |

A modular monolith gives TrackFlow **clear internal boundaries without distributed-systems
overhead** — exactly right for a single engineering team that needs cohesion across
domains (orders touch inventory, which touches carriers) far more than it needs
independent horizontal scaling.

### Why not the alternatives

- **Flat MVC / "routes + models" layout.** With ten realistic domains, a flat structure
  collapses into a few giant files and a tangle of cross-imports. It does not survive
  TrackFlow's domain count, and it is the failure mode this proposal exists to prevent.
- **Microservices now.** Splitting into independently deployed services would impose
  network calls, distributed transactions, and per-service ops on a single team solving a
  *data-unification* problem. It optimizes for a scaling pressure TrackFlow does not have
  while making the cross-domain workflows (orders → inventory → carriers) harder. The
  modular monolith keeps the *option* of extraction without paying for it prematurely —
  and the repo's plural `services/` folder already supports that future split.
- **Serverless / function-per-endpoint.** Attractive for spiky, stateless workloads;
  poorly matched to a stateful logistics core with rich cross-domain logic, shared DB
  connections, and a team that benefits from one coherent codebase. May suit isolated
  later workloads (e.g. a webhook handler), but not the Central API itself.

---

## 3. Where the Backend Lives in the Monorepo

The backend belongs at:

```text
services/central-api/
```

This honors the boundaries already established in the repo:

- **`AGENTS.md`** — "APIs and backend services go under `services/`."
- **`services/README.md`** — reserves the folder for future APIs and explicitly names
  `services/central-api/` as the expected first subfolder.
- **`services/README.md`** — the folder is *not yet an npm workspace member*; the note
  says to "add `services/*` to the root workspace list when the first service lands."
  Because the Central API is a **Python/FastAPI** service rather than a Node package, it
  will not be a true npm workspace member in the JS sense — it will be added to the
  workspace listing only insofar as tooling/orchestration needs it, and that decision is
  Engagement 5's, not this proposal's.
- **Dependency direction is preserved.** The repo rule is that `apps/` and `uis/` may
  depend on `packages/`, never the reverse. The Central API is a *peer* runtime, not a
  package the UIs import — frontends reach it over HTTP, not via a code import. It does
  not violate, and is not constrained by, the `packages/` dependency rule.

Each future backend service gets its own `services/<name>/` subfolder; the Central API is
the first.

---

## 4. Folder & Module Structure

Inside `services/central-api/`, separate **technical-layer folders** (shared mechanics)
from **business-domain folders** (one per domain). Illustrative layout:

```text
services/central-api/
├── pyproject.toml              # dependencies & tooling (Engagement 5 decides exact tool)
├── README.md                   # service-level orientation
├── .env.example                # documents required env vars (no secrets committed)
├── app/
│   ├── main.py                 # FastAPI app entrypoint: create app, mount routers, CORS
│   ├── core/                   # cross-cutting technical concerns
│   │   ├── config.py           # Settings (env-driven, pydantic-settings)
│   │   ├── dependencies.py     # shared FastAPI dependencies (DB session, current user)
│   │   └── security.py         # auth/authorization primitives
│   ├── db/
│   │   ├── session.py          # engine / session factory
│   │   └── base.py             # ORM base / metadata
│   ├── api/
│   │   └── v1/
│   │       └── router.py       # aggregates every domain router under /api/v1
│   └── domains/                # ← business partition lives here
│       ├── inventory/
│       │   ├── router.py       # APIRouter: HTTP surface only
│       │   ├── schemas.py      # Pydantic request/response models (the API contract)
│       │   ├── service.py      # business logic (the rules live here)
│       │   ├── repository.py   # data access (the only layer that talks to the DB)
│       │   └── models.py       # ORM/persistence models
│       ├── carriers/           # same internal shape
│       ├── orders/
│       ├── warehouses/
│       ├── returns/
│       ├── customers/
│       ├── support/
│       ├── reports/
│       ├── auth/
│       └── ai/                 # AI/automation interfaces (Eng. 7–9 integration seam)
└── tests/
    └── domains/                # tests mirror the domain structure
```

**Why this layout:**

- **Domain folders are the primary partition.** A new engineer or AI agent opening
  `domains/returns/` sees *everything* about returns in one place — its routes, its
  contract, its rules, its data access. This is the single most important property for a
  codebase that future AI agents must navigate and maintain.
- **Technical-layer folders (`core/`, `db/`, `api/`) hold shared mechanics** so domains
  don't each reinvent config, sessions, or auth.
- **Each domain repeats the same five-file shape** (`router / schemas / service /
  repository / models`). Predictable structure is what keeps the service from drifting
  into one big file: there is always an obvious, named place for each kind of code, so
  nothing accumulates in a route handler by default.
- **Layering is enforced by file responsibility:** routers never contain business logic;
  services never issue raw SQL; repositories are the only DB-touching layer. This is what
  makes the logic unit-testable without spinning up HTTP.

---

## 5. Domain Organization

The proposed domains map directly to TrackFlow's operational problems and stakeholders:

| Domain | Operational problem it owns | Primary stakeholder |
|---|---|---|
| `warehouses` | Two-site operations (LA, Zaragoza), locations, capacity | Ana Whitfield (Warehouse Ops) |
| `inventory` | Shared stock visibility across both warehouses, movements | Ana Whitfield |
| `orders` | Order lifecycle: pick, pack, dispatch | Warehouse Ops |
| `carriers` | Unified carrier performance (on-time, cost/kg, incidents), selection | Carlos Vega (Last Mile) |
| `returns` | Rule-driven returns approval, collection, inspection, pattern analysis | Sofia Ramos (Reverse Logistics) |
| `customers` | CRM / account management replacing spreadsheets; lead persistence | Miguel Torres (Commercial) |
| `support` | Ticketing, knowledge retrieval, first-line automation, sentiment | Valentina Cruz (Customer Experience) |
| `reports` | Automated executive reporting (replaces the manual Sunday-night build) | Thomas Harry (CEO) |
| `auth` | Authentication & authorization for the backoffice and APIs | CTO / all internal users |
| `ai` | Interfaces for future AI agents, RAG, and automation (Eng. 7–9) | TrackFlow Tech |

**Why separate them:** each domain has a distinct owner, distinct rules, and a distinct
rate of change. Isolating them means a change to returns logic cannot accidentally break
carrier scoring, and ownership maps cleanly to the people who requested each capability.

**How they connect:** domains are separated, not isolated. Real workflows cross
boundaries — e.g. **creating an order** reads `inventory`, then asks `carriers` to score
and select a carrier, then may later spawn a `returns` case. These cross-domain
interactions should go **service-to-service inside the monolith** (one domain's `service`
calling another's), never repository-to-repository or router-to-router. Keeping the
cross-talk at the service layer is what preserves the option to extract a domain later.

**Contract alignment with existing code:** the TypeScript domain model already exists in
`@repo/shared-types` (`packages/shared/src/types/index.ts`) — `Product`, `Shipment`,
`Carrier`, `InventoryMovement`, and their enums. The FastAPI Pydantic **schemas** for
`inventory`, `carriers`, and `orders` should mirror these shapes so the same domain
concept means the same thing on both sides of the wire. Keeping them in sync is a
standing concern (see §10).

---

## 6. FastAPI Router & Endpoint Organization

- **One `APIRouter` per domain**, defined in that domain's `router.py`.
- **All domain routers are aggregated** in `app/api/v1/router.py`, which is mounted once
  in `main.py`. `main.py` stays small: create the app, configure CORS, include the v1
  router.
- **Domain prefixes** are set where each router is included, producing:

  ```text
  /api/v1/inventory
  /api/v1/warehouses
  /api/v1/orders
  /api/v1/carriers
  /api/v1/returns
  /api/v1/customers
  /api/v1/support
  /api/v1/reports
  /api/v1/auth
  ```

- **Why group by domain (not by HTTP verb or by "all routes in one file"):** a domain
  router co-locates every endpoint a stakeholder cares about, keeps each file small, and
  lets FastAPI's generated OpenAPI docs group logically by tag. It is also the grouping a
  reviewer (human or AI) expects when they open the project.
- **Why route handlers stay thin:** a handler should validate input (via the schema),
  call the domain `service`, and return a response schema. No business rules, no SQL. This
  keeps the HTTP layer swappable and the logic testable.
- **Prefix handling:** prefixes are declared at include-time in the aggregator, not
  hard-coded into each path, so the whole API can be re-rooted in one place.
- **API versioning:** the `/api/v1` prefix is deliberate. New, incompatible contracts go
  under `/api/v2` (a parallel `api/v2/` aggregator) while `v1` keeps serving existing
  clients. This matters because the frontends are deployed independently and cannot be
  forced to upgrade in lockstep — versioning is how the backend evolves without breaking
  them. The existing talent tracker already calls a `/api/v1` surface
  ([`uis/backoffice/lib/talent/api.ts`](../../uis/backoffice/lib/talent/api.ts)),
  so this convention is already familiar in the codebase.

---

## 7. FastAPI Project Conventions Applied

The structure above is standard, idiomatic FastAPI, adapted to TrackFlow's domains:

- **`main.py` as the entrypoint** — constructs the `FastAPI()` app, applies CORS
  middleware, and includes the versioned router. Nothing domain-specific lives here.
- **`APIRouter` for route groups** — the mechanism that lets routes live in per-domain
  files instead of one module.
- **Schemas vs. models are separated** — Pydantic `schemas.py` defines the *API contract*
  (request/response shapes, validation); `models.py` defines *persistence*. Never return
  ORM models directly; always go through a response schema. This decouples the public
  contract from the database layout.
- **Configuration management** — `core/config.py` uses environment-driven settings
  (pydantic-settings), so the same code runs in local/staging/prod with different env
  values and no code changes.
- **Dependency injection** — FastAPI's `Depends` provides DB sessions, the current
  authenticated user, and other shared resources via `core/dependencies.py`. This keeps
  handlers clean and makes them trivially testable with overrides.
- **Separation of API routes from business logic** — the router → service → repository
  layering is the FastAPI-community-recommended way to keep handlers thin and rules
  reusable.

Standard FastAPI structure is what *shaped* this design; TrackFlow's contribution is the
**domain partition** layered on top of those conventions.

---

## 8. Frontend / Backend Separation

The frontends (`apps/`, `uis/website/`, `uis/backoffice/`) and the Central API are
**separate systems** that communicate only over HTTP:

```text
Frontend UI  →  HTTP API request (/api/v1/...)  →  FastAPI backend  →  database / services
```

- **Frontends never touch the database.** All reads and writes go through the API. This
  keeps business rules and credentials server-side, gives one auditable place for logic,
  and lets the backend evolve its storage without breaking any UI. (It is also what makes
  the deferred lead-form persistence and backoffice auth land cleanly behind the API.)
- **Base URL via environment variable.** Frontends already follow this pattern: the
  talent tracker reads `NEXT_PUBLIC_TALENT_API_URL`
  ([`uis/backoffice/lib/talent/api.ts`](../../uis/backoffice/lib/talent/api.ts))
  through a **single fetch chokepoint** with normalizers. The Central API should be wired
  the same way — one API-client module per frontend, base URL from env, no hard-coded
  hosts. The `NEXT_PUBLIC_` prefix is required for any var that must reach the browser.
- **Environment variable management.** Backend settings (DB URL, secrets, allowed
  origins) live in the service's environment, documented in `.env.example`, never
  committed. Frontend public vars are limited to what the browser legitimately needs
  (the API base URL). Secrets never appear in `NEXT_PUBLIC_` vars.
- **CORS.** The backend must explicitly allow the frontend origins. Use an **allowlist
  per environment** (local `localhost:3000`-style origins; production the real domains),
  driven by `core/config.py`. Never ship `allow_origins=["*"]` with credentials.
- **Local vs production differences.** Locally, frontends point at a local API
  (`http://localhost:8000`) and CORS allows localhost; in production they point at the
  deployed API host and CORS allows the production domains. Only env values change — not
  code.
- **Contract alignment.** The Pydantic response schemas are the contract. Keeping them
  aligned with `@repo/shared-types` (§5) means a `Carrier` or `Product` returned by the
  API matches what the TypeScript frontends already expect.

---

## 9. Risks & Points of Attention

Each risk below states the problem **and** why it matters for TrackFlow.

1. **All routes in one file.** *Problem:* a single `main.py` (or one `routes.py`)
   accumulating every endpoint. *Why it matters:* with ten domains and a small team,
   this becomes an unmergeable, unreviewable bottleneck within weeks and is exactly the
   fragmentation TrackFlow is trying to escape. The per-domain `APIRouter` structure
   prevents it.

2. **Business logic inside route handlers.** *Problem:* validation, rules, and SQL
   crammed into the endpoint function. *Why it matters:* TrackFlow's value is in
   *auditable business logic* (returns rules, carrier scoring). If those rules live in
   handlers they can't be unit-tested or reused by the future AI agents and reporting
   that need them. Logic must live in `service.py`.

3. **Weak or implicit frontend/backend contracts.** *Problem:* endpoints returning
   ad-hoc JSON instead of declared response schemas. *Why it matters:* the frontends
   deploy independently; an undocumented shape change silently breaks the backoffice or
   marketing lead capture. Pydantic schemas + OpenAPI make the contract explicit and
   versionable.

4. **Poor environment-variable management.** *Problem:* hard-coded URLs/secrets, or
   secrets leaking into `NEXT_PUBLIC_` vars. *Why it matters:* it blocks safe
   local→staging→prod promotion and risks exposing credentials in the browser bundle.
   Env-driven `config.py` and a committed `.env.example` (no secrets) are the guardrail.

5. **Incorrect CORS configuration.** *Problem:* either too open (`*` with credentials) or
   too closed (blocking the real frontends). *Why it matters:* too open is a security
   hole; too closed silently breaks every UI. A per-environment allowlist is required.

6. **Confusing / blurred domain boundaries.** *Problem:* one domain reaching directly
   into another's repository or models. *Why it matters:* it re-creates the tangle that
   makes the current spreadsheet/manual systems unmaintainable, and it forfeits the
   modular-monolith's main benefit — the ability to extract a domain later. Cross-domain
   calls go service-to-service only.

7. **Ignoring the existing monorepo structure.** *Problem:* placing backend code outside
   `services/`, or breaking the `packages/` dependency direction. *Why it matters:*
   `AGENTS.md` and the memory bank make these boundaries load-bearing for every coding
   agent; violating them erodes the very engineering discipline Engagement 4 established.

8. **Code future AI agents can't understand or maintain.** *Problem:* clever, implicit,
   or inconsistent structure. *Why it matters:* TrackFlow's roadmap (Eng. 7–9) explicitly
   has AI agents working *in* this codebase. The predictable per-domain five-file shape,
   explicit schemas, and thin handlers exist precisely so an agent can reliably locate
   and change the right code.

---

## 10. Open Items & Follow-ups (non-binding notes for the Engagement 5 brief)

These are flagged for whoever writes the Engagement 5 brief. **No action is taken here.**

- **README "Node.js" reconciliation.** The README tech-stack table currently reserves the
  `services/` boundary for *"future Node.js APIs,"* which predates the FastAPI/Python
  direction in the planning brief. The AI/data roadmap (Eng. 6–8) justifies Python. This
  line should be reconciled **when the Engagement 5 brief lands**, via the normal
  engagement-tracking-doc update workflow — not as part of this planning task.
- **Pydantic ↔ TypeScript contract sync.** Decide the mechanism for keeping FastAPI
  schemas aligned with `@repo/shared-types` (manual discipline, generated OpenAPI client,
  or generated types). Recommended to settle in Engagement 5.
- **Workspace registration.** Decide how/whether a Python service is represented in the
  npm workspace tooling, per the note in `services/README.md`.
- **Auth & lead-form persistence inflow.** `progress.md` defers backoffice auth and
  lead-form persistence to Engagement 5; both land behind this API (the `auth` and
  `customers` domains).

---

*This proposal provides the reasoning and structure needed to begin planning the Central
API. The actual scaffold, dependencies, and endpoints are Engagement 5 work, to be guided
by the brief that accompanies it.*
