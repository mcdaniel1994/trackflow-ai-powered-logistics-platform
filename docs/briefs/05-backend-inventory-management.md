# Brief: Backend Inventory Management

## Client: TrackFlow · Stakeholder: Andrés Kim (CTO)

## Status

In progress — Engagement 5. Implementation lives in `services/central-api/`.

## Background

TrackFlow operates warehouses in Los Angeles and Zaragoza for e-commerce brands that
outsource their logistics operations. Every unit received, dispatched, or written off
must be traceable because a stock discrepancy is a contractual issue, not merely an
internal inconvenience.

Each warehouse currently uses a different inventory system, so TrackFlow has no shared
authoritative stock view. Engagement 2 delivered TypeScript inventory and carrier
utilities, and Engagement 4 established the `services/` boundary. Engagement 5 now adds
the first durable logistics API and PostgreSQL persistence without changing the
delivered Engagement 2 package.

## Stakeholder Request

Andrés Kim, CTO, raised the requirement in Linear ticket TRK-0341:

> This is the foundation of everything. We need a unified inventory API for SKUs across
> both warehouses. A "stock entry" is a goods receipt from a client brand. A "stock
> exit" is a dispatch for a customer shipment or a confirmed loss. Stock is always
> computed — entries minus exits — never set directly. All routes under `/inventory`.
> The full entity spec is below. Auth stays in TinyDB.

## Assignment

Build an independently managed FastAPI service at `services/central-api/` that owns
inventory persistence in PostgreSQL through SQLModel and Alembic. Keep Identity as the
sole TinyDB owner. Protect inventory routes by verifying Identity-issued RS256 access
tokens through `packages/trackflow_auth`, and derive movement `user_uuid` values from
the authenticated principal rather than client input.

The service is a domain-oriented modular monolith beginning with inventory. It must
provide transactional stock movements, location-specific computed stock, repeatable
seed data, safe failures, and a comprehensive disposable-PostgreSQL test suite.

## What You're Building

### Service and persistence boundary

- An independent Python/FastAPI project under `services/central-api/`.
- PostgreSQL persistence managed exclusively by SQLModel models and Alembic migrations.
- Request-scoped database sessions; no application-startup `create_all()`.
- A disposable Docker PostgreSQL service for local migrations and tests.
- Environment-driven database, CORS, Identity token-verification, and seed settings.
- A public `/health` endpoint and authenticated inventory endpoints.

### Entity specification

Use these names exactly in models, schemas, and API responses.

#### `SKU` (maps to Engagement 2's `Product`)

| Field | Type | Notes |
|---|---|---|
| `id` | `int` (PK) | Auto-increment |
| `name` | `str` | Product description, e.g. `"Classic White Sneaker - Size 42"` |
| `sku` | `str` | Client-assigned code, e.g. `"CLT-SNK-W-42"` |
| `client_name` | `str` | Brand that owns the SKU, e.g. `"PureStep Footwear"` |
| `category` | `str` | `"fashion"`, `"electronics"`, or `"cosmetics"` |
| `warehouse` | `str` | `"LA"` or `"ZGZ"` |
| `current_stock` | `int` | Computed response field; never stored |

#### `StockEntry` (maps to Engagement 2's `InboundOrder`)

A goods receipt from a client brand into a TrackFlow warehouse.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` (PK) | Auto-increment |
| `sku_id` | `int` (FK → `SKU`) | Referenced inventory row |
| `quantity` | `int` | Positive units received |
| `reference` | `str` | Client dispatch reference, e.g. purchase order number |
| `warehouse` | `str` | `"LA"` or `"ZGZ"` receiving warehouse |
| `created_at` | `datetime` | UTC; auto-set on creation |
| `user_uuid` | `str` | Authenticated warehouse operative's TinyDB UUID |

#### `StockExit` (maps to Engagement 2's `OutboundOrder`)

A dispatch for customer delivery or a confirmed stock loss.

| Field | Type | Notes |
|---|---|---|
| `id` | `int` (PK) | Auto-increment |
| `sku_id` | `int` (FK → `SKU`) | Referenced inventory row |
| `quantity` | `int` | Positive units dispatched or written off |
| `exit_type` | `str` | `"dispatch"` or `"loss"` |
| `tracking_number` | `str \| None` | Required for dispatch; null for loss |
| `warehouse` | `str` | `"LA"` or `"ZGZ"` |
| `created_at` | `datetime` | UTC; auto-set on creation |
| `user_uuid` | `str` | Authenticated coordinator's TinyDB UUID |

### API contract

All inventory endpoints use the exact `/inventory` prefix.

| Method | Path | Description |
|---|---|---|
| `GET` | `/inventory/products` | Paginated SKUs with location-specific `current_stock` |
| `POST` | `/inventory/products` | Register a new SKU |
| `GET` | `/inventory/products/{id}` | Get one SKU with computed stock |
| `POST` | `/inventory/orders/inbound` | Register a goods receipt |
| `POST` | `/inventory/orders/outbound` | Register a dispatch or loss |
| `GET` | `/inventory/orders` | Paginated reverse-chronological movement timeline with SKU data |

`current_stock` is a scalar for the SKU row's warehouse. The movement timeline uses
`movement_type: "inbound" | "outbound"`, nullable movement-specific fields, and nested
SKU data.

### Business and database rules

1. `current_stock` is always computed as entries minus exits and is never stored or
   client-writable.
2. Stock is calculated per SKU row and warehouse, never aggregated across LA and ZGZ.
3. An exit that would make stock negative is rejected before writing with HTTP `400`
   and the exact message:
   `"Insufficient stock for SKU '{sku}'. Available: {available}, requested: {quantity}."`
4. Dispatch exits require a tracking number; loss exits require it to be null.
5. SKU `(sku, warehouse)` pairs are unique.
6. Movement warehouse must match the referenced SKU warehouse.
7. Quantities are positive; warehouses, categories, and exit types use the allowed
   values.
8. Every movement write locks the relevant SKU/location, computes stock inside the same
   transaction, and commits or rolls back atomically.
9. `user_uuid` is an external Identity identifier. There is no PostgreSQL user table or
   foreign key, and Central API never opens Identity's TinyDB.
10. List reads are bounded and use aggregate queries rather than per-row lookups.

### Authentication and failure behavior

- Every inventory route requires a valid active Identity-issued access token.
- Temporary-password users are rejected with `403`.
- Cookie-authenticated writes require double-submit CSRF validation; bearer-token writes
  do not.
- Unknown SKU returns `404`; duplicate SKU/location returns `409`; invalid schemas
  return `422`; warehouse mismatch returns `400`.
- Database failures return a safe `503`; internal detail is logged without credentials,
  tokens, connection URLs, or request payloads.

### Seed data

The idempotent seed command must require a valid `SEED_USER_UUID` and create at least
these six SKUs:

| name | sku | client_name | category | warehouse |
|---|---|---|---|---|
| Classic White Sneaker - Size 42 | CLT-SNK-W-42 | PureStep Footwear | fashion | LA |
| Classic White Sneaker - Size 42 | CLT-SNK-W-42-Z | PureStep Footwear | fashion | ZGZ |
| Wireless Earbuds Pro | TEC-EAR-001 | SoundWave Electronics | electronics | LA |
| Hydrating Face Serum 30ml | CSM-SRM-030 | GlowLab Cosmetics | cosmetics | ZGZ |
| Slim Fit Chino - Navy 32/32 | CLT-CHN-N-32 | UrbanThread | fashion | LA |
| USB-C Fast Charger 65W | TEC-CHG-065 | SoundWave Electronics | electronics | ZGZ |

Seed at least four entries, including two different receipts for the same SKU, with
realistic references such as `"PO-2024-0098"` and `"GR-LA-0234"`. Seed at least three
valid exits across both warehouses, including one dispatch with tracking number
`"1Z999AA10123456784"` and one loss with a null tracking number.

## Acceptance Criteria

- The independent Central API project installs and builds through `uv`.
- Alembic upgrades an empty disposable PostgreSQL database and the migration rollback
  path is verified.
- No `current_stock` column or PostgreSQL user table exists.
- All six exact inventory routes work and return the documented schemas.
- Product stock is computed per warehouse after multiple entries and exits.
- A concurrent outbound race cannot create negative stock.
- An excessive exit returns the exact required `400` message and writes no row.
- Dispatch/loss tracking rules, positive quantities, enums, foreign keys, uniqueness,
  and warehouse consistency are enforced and tested.
- `user_uuid` always comes from the verified principal and is never client-writable.
- Authentication, CSRF, temporary-password, validation, not-found, conflict, database
  failure, safe logging, pagination, ordering, and query-count behavior are tested.
- The seed command is repeatable without duplicate rows and refuses missing or malformed
  `SEED_USER_UUID`.
- Ruff, mypy, package build, pytest with coverage, migration checks, and
  `git diff --check` pass locally.
- Supabase is not migrated or seeded until the target is confirmed as disposable
  development infrastructure and explicit approval is granted.

## Out of Scope

- Inventory UI work in `uis/backoffice/`.
- Lead-form persistence.
- Carrier, returns, customer, support, reporting, or other Central API domains.
- Changes to delivered Engagement 2 behavior in `packages/shared/`.
- Moving Identity users, sessions, or authentication persistence out of TinyDB.
- Repository-wide CI, production deployment automation, or unverified production
  readiness claims.
- Running migrations or seeds against Supabase without the required confirmation and
  approval.
