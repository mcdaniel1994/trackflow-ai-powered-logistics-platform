# TrackFlow Central API

TrackFlow's independently managed FastAPI service for PostgreSQL-backed
inventory, centralized operational incidents, and suppliers.

## Delivery status

Engagement 5 inventory and the Centralized Incident Manager subproject are delivered. Engagement 6
reporting-reliability Phase 6.1 is deployed through Alembic `20260728_0011` and closed by documented
owner exception. Phase 6.2 adds `reporting.hourly_activity_rollups`, singleton `rollup_state`, and
an additive cadence identity at deployed head `20260728_0012`; its set-based production-cardinality
correction awaits redeployment and exact live reconciliation.
Engagement 8 Phases 4–6 add jurisdiction-bound agent retrieval, layered input/output guardrails,
creator-owned delegated incident access, safe guardrail aggregates, and human-confirmed structured
memory at Alembic head `20260803_0016`. Phase 6 safely captures routing-model usage, derives run
totals from the accounted graph step exactly once, and prunes one bounded batch of expired traces
through daily maintenance. The release suite covers disposable-PostgreSQL
migration rollback, repeatable seeds, security and failure paths, reporting attempts and health
separation, aggregate queries, lifecycle transitions, and concurrent inventory/incident
protection. The Phase 6 Central API gate is 286 passing tests with 91.55% branch-aware source
coverage.

The August 3 disposable local MCP owner-review exercise verified delegated test-ticket operations,
inventory list/get, local `INVENTORY_READ_ONLY` enforcement with no inventory delete reaching this
service, and `INSUFFICIENT_SCOPE` without `incidents:write`. The safe evidence record is
[`docs/agents/mcp-owner-review-evidence-2026-08-03.md`](../../docs/agents/mcp-owner-review-evidence-2026-08-03.md);
it was not a Codespaces or production exercise. The owner accepted this evidence and closed
Engagement 8 on August 3, 2026, explicitly waiving rather than passing the unexecuted
Codespaces-specific exercise.

Routing cost is computed only for models in the explicit `MODEL_PRICES` configuration. The
`gpt-4o-mini` and pinned `gpt-4o-mini-2024-07-18` prices were verified on August 3, 2026 against
OpenAI's official [Prompt Caching pricing table](https://openai.com/index/api-prompt-caching/).
Unknown prices keep safe token counts and leave cost null; absent or malformed usage leaves both
fields null without failing the agent request. No prompt, completion, or provider payload is stored.

`POST /agent/query` accepts `question`, optional `conversation_id`, and an optional typed
`memory_decision` (`decision_id`, `proposal_id`, and `approve`, `reject`, or `edit`). Edits require a
complete replacement candidate and remain pending until a later typed approval. The response always
returns `answer`, `trace_id`, `conversation_id`, and the exact pending `memory_proposal` when one
exists; plain text, including “yes,” never approves memory.

The portfolio Supabase production project is migrated through Alembic revision
`20260728_0011` as of the July 28 production acceptance rescan. Runtime-role CRUD, Central API
health, approved
inventory and supplier seeds, and authenticated Back Office access are verified; the weekly
business report has never successfully published. Future production changes and restore drills remain
approval-gated through `docs/runbooks/`.

Engagement 10 Part 1 adds an application-scoped, bounded in-process real-time bus and
`GET /realtime/rfp/stream`. The async SSE handler authenticates only from the existing host-only
access cookie, scopes subscriptions to `rfp.tickets.<owner_user_uuid>`, sends keep-alive comments,
and closes at JWT expiry. RFP creation publishes `rfp_ticket_created` after the initial ticket commit
and before background intake; this notification path imports or calls no model, RAG, or agent code.
`RFP_ENABLED` gates the endpoint and remains off by default.

Engagement 10 Phase 3 adds owner-scoped `chat_sessions` and ordered `chat_messages` at additive
Alembic head `20260818_0018`. Database constraints fix the agent identity to `first_line_cx`, enforce
session/message states, and prevent duplicate per-session sequences. Repository reads require the
owner `user_id`; message inserts allocate sequence numbers under a session row lock. The daily
maintenance worker deletes one bounded batch of sessions inactive for more than 90 days and relies
on cascade deletion for their messages. Message content is approved user-facing product history,
not telemetry, and is never copied into traces or logs. WebSocket transport and chat APIs were
deferred at that boundary. Phase 4 adds owner-scoped create/list/detail HTTP endpoints and threads chat
session IDs through the existing agent query path. Each successful HTTP turn persists ordered user
and assistant messages while suppressing trace content summaries, and the response reports the
route actually used. Auto keeps existing classifier behavior; Knowledge base and Ticket lookup pin
the existing routes without changing the agent or its tools. Phase 5 adds
`/realtime/chat/{session_id}`: the same host-only JWT cookie authenticates the upgrade before accept,
the session is rechecked as owner-scoped, and a subscribe-before-snapshot sequence closes reconnect
gaps. One application-scoped generation manager produces guarded DeepSeek answer deltas for every
subscriber. Interrupt closes the provider stream, persists any partial assistant message as
interrupted, and optionally starts the redirected input as a new turn. Raw chat content remains out
of logs and agent traces.

## Ownership and boundaries

- Central API owns inventory SKUs and stock movements in PostgreSQL.
- Central API owns operational incidents, lifecycle transitions, and summary metrics.
- Central API owns owner-scoped chat sessions and their 90-day message history.
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
| `IDENTITY_OAUTH_ISSUER_URL` | Public URL issuer for scoped OAuth resource tokens |
| `IDENTITY_OAUTH_INTERNAL_URL` | Internal Identity origin used only for delegated token exchange |
| `CENTRAL_API_OAUTH_RESOURCE_URL` | Exact public audience accepted on incident and read-only inventory routes |
| `AGENT_MCP_URL` | Internal Streamable HTTP transport URL used by the LangGraph ticket node |
| `AGENT_MCP_RESOURCE_URL` | Public MCP resource identifier requested during token exchange |
| `AGENT_MCP_OAUTH_CLIENT_ID` / `AGENT_MCP_OAUTH_CLIENT_SECRET` | Confidential Central API client provisioned through Identity; never logged or persisted in graph state |
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
