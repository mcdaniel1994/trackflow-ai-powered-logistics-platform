# TrackFlow Central API

TrackFlow's independently managed FastAPI service for PostgreSQL-backed
inventory, centralized operational incidents, and suppliers.

## Delivery status

Engagement 5 inventory and the Centralized Incident Manager subproject are delivered. Engagement 6
reporting-reliability Phase 6.1 is implemented locally through Alembic `20260728_0011`; its
persisted-log defaults are owner-approved and it awaits production acceptance before Phase 6.2.
The release suite covers disposable-PostgreSQL
migration rollback, repeatable seeds, security and failure paths, reporting attempts and health
separation, aggregate queries, lifecycle transitions, and concurrent inventory/incident
protection. The current Central API baseline is 173 passing tests with 93% branch-aware source
coverage.

The portfolio Supabase production project is migrated through Alembic revision
`20260716_0010` as of the July 28 read-only rescan. Runtime-role CRUD, Central API health, approved
inventory and supplier seeds, and authenticated Back Office access are verified; the weekly
business report has never successfully published. Future production changes and restore drills remain
approval-gated through `docs/runbooks/`.

## Ownership and boundaries

- Central API owns inventory SKUs and stock movements in PostgreSQL.
- Central API owns operational incidents, lifecycle transitions, and summary metrics.
- Identity remains the sole owner of TinyDB users and sessions.
- Central API verifies Identity-issued RS256 access tokens through
  `packages/trackflow_auth`; it never opens Identity's TinyDB.
- All inventory routes use the exact `/inventory/...` paths from the engagement brief.
- Incident routes use `/api/incidents...` and remain a subproject rather than a
  numbered engagement.

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
uv run --project services/central-api seed-incidents \
  services/central-api/tests/fixtures/sample-incidents.csv
uv run --project services/central-api uvicorn central_api.main:app --reload --port 8002
```

Local liveness: `http://127.0.0.1:8002/health/live`. Readiness is
`/health/ready`; `/health` retains the original compatibility response. Core readiness verifies
only the database, image schema floor, inventory columns, and production runtime role. Reporting
grants, worker/orchestrator state, queue state, publication time, and safe latest failure evidence
are isolated on `/health/reporting` and never trigger application rollback.
The maintenance image also runs API-only Prefect terminal-run retention; the separate
`prefect-db-backup` image owns `pg_dump` and backup R2 access so Central API never receives either.
Reporting status uses one shared derivation for the reporting verification/API six-state
`queue_state`. The reporting worker enforces the image-baked Prefect PostgreSQL and version
contract fail-closed before claiming work; one-shot guards report but do not gate Compose startup.
Container health uses `/health/live`; core `/health/ready` is the release gate.

## Quality gates

```bash
uv run --project services/central-api ruff check services/central-api
uv run --project services/central-api mypy services/central-api/central_api
uv build --project services/central-api
uv run --project services/central-api pytest -c services/central-api/pyproject.toml \
  services/central-api/tests --cov=central_api --cov-report=term-missing
```

Migration, seed, integration, and concurrency tests target the disposable PostgreSQL
database from `compose.yml`. Never run future migrations or seeds against Supabase
without confirming the target, recovery posture, and explicit approval.

## Configuration

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | SQLAlchemy PostgreSQL URL |
| `MIGRATION_DATABASE_URL` | Dedicated migration-role URL; mandatory for Alembic in production and never supplied to runtime containers |
| `APP_ENV` | `production` enables fail-closed migration-role and readiness checks |
| `RUNTIME_DATABASE_ROLE` | Expected production runtime identity; defaults to `trackflow_runtime` |
| `CENTRAL_API_CORS_ORIGINS` | Comma-separated trusted browser origins |
| `IDENTITY_JWT_PUBLIC_KEY` | Identity RS256 public key; escaped newlines are accepted |
| `IDENTITY_JWT_ALGORITHM` | Must remain `RS256` |
| `IDENTITY_JWT_ISSUER` | Expected access-token issuer |
| `IDENTITY_JWT_AUDIENCE` | Expected access-token audience |
| `SEED_USER_UUID` | Existing local Identity user's UUID for seeded movements |
| `PREFECT_API_URL` | Internal Prefect API used by maintenance retention; no Prefect DB credential |
| `PREFECT_RUN_RETENTION_DAYS` | Terminal Prefect history retention, default 30 days |
| `REPORTING_LOG_PATH` | Reporting-worker persisted log file; production uses `/var/log/trackflow/reporting/reporting-worker.log` and stdout remains active |
| `REPORTING_LOG_MAX_BYTES` / `REPORTING_LOG_BACKUP_COUNT` | Per-file rotation limits; production uses 10 MiB and 9 backups |
| `REPORTING_LOG_RETENTION_DAYS` / `REPORTING_LOG_TOTAL_BYTES` | Daily maintenance caps; production uses 14 days and 250 MiB |

Stock is computed from movements per SKU row and warehouse. It is never stored or
accepted from clients.

The seed command validates `SEED_USER_UUID` syntax and writes that external identifier
without opening Identity's TinyDB. Before running it, choose an existing user UUID from
the local Identity service. Because the databases are deliberately isolated, PostgreSQL
cannot enforce that cross-service reference.

`seed-incidents` validates the complete legacy export, stores only normalized incident
fields and a SHA-256 idempotency key, and reports aggregate counts plus safe row/field
rule identifiers. Never run it against `scripts/incidents-trackflow.csv` without the
explicit authorization required by `.agents/rules/sensitive-local-datasets.md`.
