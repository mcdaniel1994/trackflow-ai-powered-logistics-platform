# Engagement 5 — Backend Inventory Management Implementation Plan

## Summary

Build Engagement 5 as an independent FastAPI modular monolith at
`services/central-api/`. Inventory data lives in Supabase PostgreSQL through SQLModel;
Identity retains exclusive ownership of TinyDB. Central API verifies Identity-issued
tokens through `packages/trackflow_auth` and records the authenticated principal's UUID
on stock movements.

The primary brief controls naming and routes: `SKU`, `StockEntry`, `StockExit`, and exact
`/inventory/...` paths.

## 1. Initialize Engagement 5 Documentation

- Convert `docs/briefs/05-backend-inventory-management.md` into the canonical
  stakeholder-voice structure while preserving its entity specifications, business
  rules, seed requirements, and evaluator notes.
- Mark Engagement 5 active in the root roadmap, briefs index, `CLAUDE.md`, and
  `memory-bank/progress.md`; add Central API to `memory-bank/techContext.md`.
- Reconcile stale "future Node.js API" and generic "Central API" language with the
  selected Python/FastAPI inventory implementation.
- Mark the applicable parts of `docs/planning/architecture-api.md` as superseded by the
  Engagement 5 brief: `/inventory` replaces `/api/v1/inventory`, while the
  modular-monolith and service-isolation rationale remains authoritative.
- Move lead-form persistence out of Engagement 5's planned scope without assigning it
  to an invented engagement.

## 2. Service Architecture and Documentation

Create an independently managed `uv` project:

```text
services/central-api/
├── README.md
├── pyproject.toml
├── uv.lock
├── .env.example
├── compose.yml
├── alembic.ini
├── migrations/
├── central_api/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── dependencies.py
│   ├── db/
│   │   └── session.py
│   └── domains/inventory/
│       ├── models.py
│       ├── schemas.py
│       ├── repository.py
│       ├── service.py
│       ├── router.py
│       └── seed.py
└── tests/
```

- Use FastAPI, SQLModel, PostgreSQL, Alembic, `psycopg2-binary`,
  `pydantic-settings`, and the local `trackflow-auth` package.
- Add Ruff, mypy, pytest, pytest-cov, and HTTPX as development dependencies.
- Provide disposable PostgreSQL through `compose.yml` for migrations, integration
  tests, and concurrency tests.
- Configure request-scoped SQLModel sessions through FastAPI dependencies; never use a
  global session.
- Configure `DATABASE_URL`, JWT verification settings, CORS origins, and
  `SEED_USER_UUID` through environment variables.
- Keep `.env` and database credentials untracked.

Expand `services/README.md` to explain:

- Each backend service has independent ownership, dependencies, runtime, persistence,
  tests, deployment lifecycle, and failure boundary.
- The `services/` root is organizational and contains no shared runnable application.
- `identity`, `supplier-directory`, and `incident-processor` remain separate deployable
  peers.
- `central-api` is a modular monolith for closely related core logistics domains,
  beginning with inventory.
- Central API communicates with Identity through signed tokens rather than directly
  opening Identity's TinyDB file.
- Python services are independent `uv` projects, not npm workspaces.

## 3. Persistence and Inventory Rules

Implement three SQLModel tables:

- `SKU`: `id`, `name`, `sku`, `client_name`, `category`, and `warehouse`.
- `StockEntry`: `id`, `sku_id`, positive `quantity`, `reference`, `warehouse`, UTC
  `created_at`, and `user_uuid`.
- `StockExit`: `id`, `sku_id`, positive `quantity`, `exit_type`, nullable
  `tracking_number`, `warehouse`, UTC `created_at`, and `user_uuid`.

Database invariants:

- Do not create a stored `current_stock` column.
- Enforce unique `(sku, warehouse)` combinations.
- Enforce foreign keys from movements to SKUs.
- Ensure movement warehouse matches the referenced SKU warehouse using a composite
  database constraint plus service validation.
- Add database checks for positive quantities, valid warehouses/categories/exit types,
  and tracking-number requirements.
- Index movement lookups by SKU, warehouse, and creation time.
- Keep `user_uuid` as an external Identity identifier with no PostgreSQL user table or
  foreign key.

Use Alembic migrations for schema creation. `SQLModel.metadata.create_all()` may be used
only for isolated test helpers, never application startup or shared Supabase
environments.

For every movement write:

1. Lock the relevant SKU/location row.
2. Validate the warehouse and movement rules.
3. Compute available stock inside the same transaction.
4. Insert the movement.
5. Commit atomically or roll back entirely.

This prevents concurrent outbound requests from producing negative stock.

## 4. Public API Contract

Expose a public health endpoint and protect every inventory endpoint with
`trackflow_auth`. Cookie-authenticated POST requests also require CSRF validation.

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/health` | Safe service/database readiness response |
| `GET` | `/inventory/products` | Paginated SKU rows with location-specific `current_stock` |
| `POST` | `/inventory/products` | Create an SKU; `201` |
| `GET` | `/inventory/products/{id}` | Retrieve one SKU and computed stock |
| `POST` | `/inventory/orders/inbound` | Record a stock entry; `201` |
| `POST` | `/inventory/orders/outbound` | Record a dispatch or loss; `201` |
| `GET` | `/inventory/orders` | Paginated reverse-chronological movement timeline |

Contract decisions:

- `current_stock` is a scalar for that SKU row's warehouse.
- Product creation starts at zero stock.
- `user_uuid` is never accepted from clients; it comes from the verified principal.
- The orders endpoint returns a flat timeline with
  `movement_type: "inbound" | "outbound"`, movement-specific nullable fields, and
  nested SKU data.
- List endpoints accept bounded `limit` and `offset` parameters.
- Inventory queries use aggregate joins/subqueries rather than per-record lookups.

Failure behavior:

- Unknown SKU: `404`.
- Duplicate `(sku, warehouse)`: `409`.
- Invalid quantities or tracking combinations: `422`.
- Movement/SKU warehouse mismatch: `400`.
- Insufficient stock: exact required `400` message.
- Authentication failure: `401`; blocked temporary-password user or CSRF failure:
  `403`.
- Database failure: safe `503` response with internal detail logged without credentials
  or sensitive payloads.

## 5. Seed, Tests, and Release Gates

Create an idempotent seed command containing the required six SKUs, four entries, and
three exits. Require a valid `SEED_USER_UUID` belonging to a local Identity user; refuse
to seed movements when it is missing or malformed.

Test against disposable PostgreSQL:

- Alembic upgrade from an empty database and migration rollback.
- Seed repeatability without duplicate records.
- All six routes, response schemas, pagination, ordering, and nested SKU data.
- Computed stock after multiple entries and exits.
- Separate LA and ZGZ balances for the same SKU code.
- No stored or client-writable stock field.
- Positive quantities, category/warehouse enums, tracking rules, foreign-key
  enforcement, and warehouse consistency.
- Exact insufficient-stock response and verification that no row was written.
- Concurrent outbound requests cannot produce negative stock.
- Authentication on every inventory route, CSRF on cookie-backed writes, bearer-token
  writes, and temporary-password rejection.
- `user_uuid` always comes from the authenticated principal.
- Database failures produce safe responses and logs without URLs, credentials, tokens,
  or payload data.
- Query behavior avoids N+1 loading for products and movements.

Required local gates:

- Ruff lint passes.
- mypy passes.
- Package build succeeds.
- pytest and coverage pass without untested failure paths.
- Alembic migrations run cleanly against disposable PostgreSQL.
- `git diff --check` passes.
- A Supabase development smoke test is performed only after confirming the target is
  disposable/non-production and credentials are available; no remote migration runs
  without that approval.

## Assumptions and Boundaries

- No Back Office inventory UI is included.
- No lead-form persistence, carrier, returns, or other Central API domains are included.
- Existing services are not merged or migrated.
- Identity remains the sole TinyDB owner; Central API does not perform direct TinyDB
  reads.
- Any authenticated active user may access inventory routes; role and warehouse-scoped
  authorization are deferred until a permission matrix exists.
- Existing Engagement 2 TypeScript types remain untouched; API adapters can be added
  when a UI consumes this service.
- Production deployment automation, runbooks, and repository-wide CI remain follow-ups;
  Engagement 5 uses documented local gates.
- Preserve all unrelated working-tree changes and do not rewrite delivered briefs or
  shared package behavior.
