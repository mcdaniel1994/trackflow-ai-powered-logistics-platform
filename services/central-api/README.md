# TrackFlow Central API

Engagement 5's independently managed FastAPI service for PostgreSQL-backed inventory
management across the Los Angeles (`LA`) and Zaragoza (`ZGZ`) warehouses.

## Ownership and boundaries

- Central API owns inventory SKUs and stock movements in PostgreSQL.
- Identity remains the sole owner of TinyDB users and sessions.
- Central API verifies Identity-issued RS256 access tokens through
  `packages/trackflow_auth`; it never opens Identity's TinyDB.
- The current engagement implements only the inventory domain. Inventory UI,
  lead-form persistence, carriers, returns, and other domains are out of scope.
- All inventory routes use the exact `/inventory/...` paths from the engagement brief.

The internal dependency direction is:

```text
router (HTTP) -> service (business rules) -> repository (queries) -> SQLModel
```

## Local prerequisites

- Python 3.11 or newer
- `uv`
- Docker with Compose

Copy `.env.example` to an untracked `.env`, replace its local-only database password,
and provide the Identity RS256 public key before exercising protected routes.

## Setup

```bash
docker compose -f services/central-api/compose.yml up -d
uv sync --project services/central-api --extra dev
uv run --project services/central-api alembic -c services/central-api/alembic.ini upgrade head
uv run --project services/central-api seed-inventory
uv run --project services/central-api uvicorn central_api.main:app --reload --port 8002
```

Local health endpoint: `http://127.0.0.1:8002/health`

## Quality gates

```bash
uv run --project services/central-api ruff check services/central-api
uv run --project services/central-api mypy services/central-api/central_api
uv build --project services/central-api
uv run --project services/central-api pytest -c services/central-api/pyproject.toml \
  services/central-api/tests --cov=central_api --cov-report=term-missing
```

Migration, seed, integration, and concurrency tests target the disposable PostgreSQL
database from `compose.yml`. Do not run migrations or seeds against Supabase until the
target is confirmed as disposable development infrastructure and explicit approval is
given.

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL |
| `CENTRAL_API_CORS_ORIGINS` | Comma-separated trusted browser origins |
| `IDENTITY_JWT_PUBLIC_KEY` | Identity RS256 public key; escaped newlines are accepted |
| `IDENTITY_JWT_ALGORITHM` | Must remain `RS256` |
| `IDENTITY_JWT_ISSUER` | Expected access-token issuer |
| `IDENTITY_JWT_AUDIENCE` | Expected access-token audience |
| `SEED_USER_UUID` | Existing local Identity user's UUID for seeded movements |

Stock is computed from movements per SKU row and warehouse. It is never stored or
accepted from clients.

The seed command validates `SEED_USER_UUID` syntax and writes that external identifier
without opening Identity's TinyDB. Before running it, choose an existing user UUID from
the local Identity service. Because the databases are deliberately isolated, PostgreSQL
cannot enforce that cross-service reference.
