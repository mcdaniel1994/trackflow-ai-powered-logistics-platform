# Engagement 8 (LangGraph) — Handoff for a fresh session

You are continuing **Engagement 8 — Agent Engineering (LangGraph)** on the TrackFlow monorepo
(`/Users/corymcdaniel/Projects/trackflow`), branch **`engagement-8-agentic-engineering`**. Phases 0–2
are built, verified, and committed (not pushed). Your job: **build the remaining phases 3–6**, one at
a time, each ending with an owner-review pause.

## Read first (in order)
1. `docs/agents/agent-design.md` — the proposed spec / design (this IS the spec; Engagement 8 had no
   prior owner-approved spec). Phase status is tracked in its "Phases" section.
2. `docs/agents/langgraph-explainer.md` — concepts + the Mermaid architecture diagram.
3. The auto-memory index `MEMORY.md` (loads automatically) — see `engagement-8-langgraph-plan` and
   `engagement-8-phase0-reorg`.
4. Planning inputs: `docs/planning/remaining_planning/08_agent_engineering/01–05` (requirements, not
   architecture) and `docs/planning/remaining_planning/README.md` (precedence rule: an approved spec
   and repo/production reality win over a planning input; surface graded-requirement conflicts to the
   owner Cory, don't silently drop either).
5. `AGENTS.md`, `CLAUDE.md`, and the relevant `.agents/rules/*` + `docs/standards/*` before each area
   (compliance-licensing for deps, telemetry for traces, database-engineering for schema,
   authentication-security for agent context, testing-error-handling-ci).

## What's already done (commits on this branch, newest first)
- `0bb723e` **Phase 2 — tools + routing**: OpenAI `gpt-4o-mini` router (`domains/agents/routing.py`,
  regex-heuristic fallback when no key), in-process ticket-status tool
  (`domains/agents/tools/incidents.py`, explicit timeout, honest fallback), graph `route` +
  `ticket_tool` nodes, tool result folded into generation as a context block, `tool_call` traces.
- `be356d1` **Phase 1 — LangGraph migration + trace store**: explicit graph
  (`domains/agents/graph.py`: `receive_question → route → retrieve|ticket_tool → generate|no_context`),
  self-hosted Postgres trace store (`agent_runs`/`agent_node_steps`/`agent_tool_calls`, migration
  `20260730_0014`, off-path `recorder.persist_run`), `POST /agent/query` + `GET /agents/runs[/{trace_id}]`.
- `be43ac5` deps (langgraph, langchain-openai — MIT, recorded in `THIRD_PARTY_LICENSES.md`).
- `35502eb` extracted `generate_answer()` from `rag.query()` (behavior-preserving).
- `4faa820` **Phase 0 — reorg** + the two `docs/agents/` docs.

## Locked decisions (owner-approved)
- Agent LLM = **OpenAI `gpt-4o-mini`** (existing key; no new provider).
- Tracing = **self-hosted Postgres** trace store (no LangSmith; `langsmith` is a transitive dep and
  is disabled-by-design — never set `LANGSMITH_*`/`LANGCHAIN_TRACING*`).
- Memory backend (Phase 5) = **Postgres structured**.
- Agent graph lives in the **central-api `agents` domain** (not `data/pipelines/`), so langgraph is a
  central-api-only dep. Agent tests live in `services/central-api/tests/` (not `tests/pipelines/`).
- Reorg is done as an additive/shim reorg; **do not move the graded/spec-pinned test paths**
  (`tests/pipelines/test_{pipeline,sales_forecasting,rag}.py` are re-export shims — see
  `engagement-8-phase0-reorg` memory).

## Remaining phases to build (each = its own commit + owner pause)

### Phase 3 — MCP server + OAuth (`03_mcp_server.md`)
- New **top-level `mcps/` uv project** (Python + **FastMCP**), NOT under `services/`.
- **OAuth via `mcpauth`** is mandatory (NOT FastMCP's built-in auth): mount Protected Resource
  Metadata, validate bearer JWTs against an OAuth 2.1/OIDC provider, reject unauthenticated calls,
  per-tool scopes, distinct documented error codes, log every tool invocation.
- Tools: **ticket** (create/update/check — status changes via `PATCH /api/incidents/{id}/status`,
  the lifecycle endpoint), **inventory** (read-only *by design* — writes explicitly rejected). Each
  ships discovery docs (name/description/I-O schema).
- **Decisions to confirm with owner at this phase**: transport (**recommend Streamable HTTP** — the
  assignment validates via a public Codespaces-forwarded URL in MCP Playground, not localhost); the
  **OAuth issuer** `mcpauth` validates against (**recommend TrackFlow's own Identity service**,
  `services/identity/`, which already issues RS256 JWTs).
- Migrate the agent's `ticket_tool` node to call the MCP server via `langchain-mcp-adapters` and
  **remove the in-process direct incidents call** ("no two paths to the Incidents Manager").
- Incidents API contract (confirmed): `GET /api/incidents`, `GET /api/incidents/{id}`,
  `PATCH /api/incidents/{id}/status`; `IncidentService(session).get(id) -> IncidentRead{id,status,
  category,created_at,updated_at,...}`; `IncidentError(status_code,code,message)`. Inventory read:
  `GET /inventory/products`, `GET /inventory/products/{sku_id}`; `InventoryService(session)`.
- Install deps with `uv add` (never `pip install`); apply compliance-licensing for FastMCP/mcpauth/
  langchain-mcp-adapters.

### Phase 4 — Guardrails (`04_harness_*.md`) — MUST precede Phase 5
- First-line CX agent for **Valentina Cruz**, B2B + B2C, **US and Spain**. Multiple guardrail layers
  ("one is never enough"): secure system prompt (system/user separation, un-modifiable, ≥3 documented
  jailbreak variants); content/scope (decline+redirect personal-chatbot use); anti-injection
  (isolate tool/RAG text; reject instruction-change in ≥3 phrasings); **authorization** (an order/
  tracking not belonging to the session ⇒ authz failure, not "no data"); **country-policy** non-mixing
  (US vs Spain); output validation before returning (no leaked instructions / carrier rates /
  warehouse locations). Log every block/redirect by type (structural/content/security); expose a
  trigger-count summary. **Automated test that fails the build if the agent obeys the mandated
  injection cases.** Add `guardrail_input`/`guardrail_output` graph nodes; populate
  `agent_run.guardrail_trigger_count`.

### Phase 5 — Memory (`05_memory_*.md`) — after guardrails
- Postgres structured memory **consolidated by carrier+country** (8 carriers × 2 countries), explicit
  read/write interface (NOT system-prompt accumulation). **Never store** (B2B & B2C): exact addresses,
  warehouse routes, single non-repeating incidents, active contract-negotiation data (tested).
  `memory_selfeval` node emits a structured `memory_proposal` in the SAME model call (no 2nd model);
  most runs ⇒ "nothing to remember" (≥3 documented). When memorable, **propose to the user in
  conversation** (never write directly); classify the next message approve/reject/edit (reuse the
  guardrails intent classifier); one pending proposal at a time; silence/ambiguity/topic-change ⇒
  discard; audit-log every decision. Poisoning resistance (guardrails-first + human gate + never-store
  rule). ≥2 full cycles (approved+reflected, rejected+unchanged). Branch note in assignment:
  `w23-d67-agent-memory`.

### Phase 6 — Agent OS dashboard (Back Office UI)
- Turn `uis/backoffice/app/(protected)/agent-os/page.tsx` (currently a placeholder) into a real
  observability dashboard over the trace store, modeled on the mock
  `docs/planning/remaining_planning/07_rag_knowledge_base/d3f5ffdf-...png`. Show: agent list, per-run
  trace view (the node/edge path as a stepper — generalize the mock's "RAG Pipeline Status" stepper),
  tools used, per-step timing/latency, token/cost, status/errors, final output. Reuse the frontend
  pattern: `lib/agents/api.ts` → `app/api/agents/[[...path]]/route.ts` (allowlist proxy) →
  `centralAPIURL()`, and `lib/hooks/useAutoRefresh.ts`. Light/dark + loading/error states, hand-rolled
  Tailwind design system. Data source: `GET /agents/runs` + `/agents/runs/{trace_id}` (already built).
- Also wire **token/cost capture** (currently null — capture the routing LLM's `usage_metadata` via a
  callback) and the **retention pruner** (a scheduled runner calling
  `AgentRepository.delete_before(cutoff)`; setting `agents_trace_retention_days=7` exists) as part of
  finishing the observability story.

## Conventions you MUST follow (learned this engagement)
- **Per phase**: run the FULL central-api suite (not just agent tests) against a real Postgres, run
  `alembic -c services/central-api/alembic.ini check` (migrations must match models — a Phase 1
  migration silently broke `test_production_migrate.py`'s head assertion; the full suite catches it),
  and run ruff + mypy. All green before committing.
- **Testing**: mock the LLM + tools in CI unit tests (no live provider); live-provider evals are
  manual/opt-in (mirror `scripts/rag_eval.py`). Add agent tables to the `clean_database` TRUNCATE in
  `tests/conftest.py` for any new table. `mypy python_version=3.11`; the LangGraph/numpy stubs are
  skipped via a `[[tool.mypy.overrides]]` block (follow_imports=skip) — extend it for new typed 3rd-party
  libs if mypy follows into 3.12-syntax stubs.
- **Telemetry §8**: traces store safe metadata only — never raw prompts/completions/retrieved text/
  tool arguments/secrets/addresses/carrier rates. Content previews are opt-in via
  `AGENTS_STORE_CONTENT` (default off). Trace writes are off the request path and swallow failures.
- **Style**: ruff line-length 120; domain triad = router/service/schemas/config (+ models/repository/
  recorder for DB); typed `XError(status_code, detail)` dataclass mapped by an
  `@app.exception_handler` in `main.py`; register routers + import models in `migrations/env.py`.
- **Git**: commit per phase with a descriptive body; end messages with
  `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`. **Do not push** unless Cory asks. Each
  phase ends with an **owner-review pause** — stop and report, don't chain phases silently.
- Surface genuine decisions with a question (don't guess); don't fabricate secrets or make paid calls
  without owner consent.

## Known gaps / deviations (carry forward)
- `total_tokens`/`total_cost_usd` and per-node `tokens`/`cost_usd` are null (routing LLM usage not
  captured yet) — fix in Phase 6.
- Inventory **stretch** tool (Part 2 optional) is deferred.
- Retention pruner not scheduled yet (method + setting exist).
- Agent tests live in `services/central-api/tests/test_agents_{graph,api,tools}.py` (deviation from the
  assignment's `tests/pipelines/` assumption — the graph is a central-api service).

## Local run (to see it working / demo traces)
There is an **untracked** local dev setup (do not commit): root `.env` (dev Postgres creds + a
throwaway RS256 JWT keypair, keys stored `\n`-escaped) and `compose.override.yml` (wires RAG/agent env
into central-api). The **identity Docker image has a file-permission bug**, so identity + Back Office
run **locally**, central-api can too:
- Postgres via compose (`docker compose up -d postgres`, port 55432) or plain `docker run`.
- Qdrant via **plain** `docker run -d --name tf-qdrant -p 6333:6333 qdrant/qdrant:v1.12.4` (compose
  was flaky), then index: `QDRANT_URL=http://localhost:6333 RAG_ENABLED=true uv run --project
  services/central-api rag-index` (paid OpenAI embeddings; 4 docs → 14 chunks).
- Migrate: `DATABASE_URL=postgresql+psycopg2://trackflow:trackflow_local_only@localhost:55432/trackflow_inventory`
  `MIGRATION_DATABASE_URL=$DATABASE_URL uv run --project services/central-api alembic -c
  services/central-api/alembic.ini upgrade head`.
- Provider keys live in `services/central-api/.env` (auto-loaded by central-api Settings).
- central-api (local): `uv run --project services/central-api uvicorn central_api.main:app --port 8003`
  with `DATABASE_URL`, `QDRANT_URL=http://localhost:6333`, `RAG_ENABLED=true`, `AGENTS_ENABLED=true`,
  `IDENTITY_JWT_PUBLIC_KEY=$(cat <keypair public.pem)`.
- identity (local): `uv run --project services/identity uvicorn identity.main:app --port 8002` with the
  keypair (`IDENTITY_JWT_PRIVATE_KEY`/`PUBLIC_KEY`), `IDENTITY_DB_PATH=<scratch>/identity.json`,
  `AUTH_COOKIE_SECURE=false`, `FRONTEND_BASE_URL=http://localhost:3000`. Create an admin via
  `identity.cli create_admin(name, email, password)`.
- Back Office (local): from `uis/backoffice`, `CENTRAL_API_URL=http://localhost:8003
  IDENTITY_API_URL=http://localhost:8002 AUTH_COOKIE_SECURE=false npm run dev` → **http://localhost:3000**.
- Demo login accounts (match the login page autofill): `corymcdaniel01@gmail.com` / `password123` and
  `employee@trackflow.com` / `password123`.
- These local dev servers are session-scoped background processes; they get killed at session
  boundaries — restart as needed.

Start by reading the files above, confirm the Phase 3 decisions (transport + OAuth issuer) with Cory,
then build Phase 3 and pause for review.
