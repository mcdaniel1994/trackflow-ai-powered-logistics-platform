# Claude-Specific Orientation

Claude-specific orientation for AI coding agents working in this repo. For the cross-agent operating rules every agent must follow, read `AGENTS.md` first.

Claude sessions should read, in order:

1. `memory-bank/projectbrief.md`
2. `memory-bank/techContext.md`
3. `memory-bank/progress.md`
4. `AGENTS.md`
5. `README.md`
6. `CLAUDE.md`

Then read the active engagement brief and the README for every folder being modified.

## Repo Navigation

| If you're looking for... | Go here |
|---|---|
| Cross-agent operating rules | `AGENTS.md` |
| Persistent project context | `memory-bank/` |
| What this project is | `README.md` |
| Repo license and third-party dependency attribution | `LICENSE`, `THIRD_PARTY_LICENSES.md` |
| Current engagement brief when assigned | `docs/briefs/NN-title.md` |
| All briefs | `docs/briefs/` |
| Cross-cutting standards and guidance | `docs/` |
| Engineering quality and telemetry standards (testing, error handling, observability, telemetry, production readiness) | `docs/standards/` |
| Operational runbooks (deployment, etc.) | `docs/runbooks/` |
| Intended CI workflow architecture | `.github/workflows/README.md` |
| Repo-specific quality remediation/improvement plans | `docs/planning/` |
| **All remaining work — specs, planning inputs, sequence** | **`docs/planning/remaining_planning/README.md`** |
| Archived planning artifacts | `docs/archive/` |
| Coding-agent scoped rules and skills | `.agents/` |
| Forward-looking UI workspace | `uis/` |
| Future backend services and APIs | `services/` |
| Engagement 1 surface (original app retired June 2026) | `uis/website/` + `docs/archive/marketing-site-retirement.md` |
| Engagement 3 tracker (standalone app retired June 2026) | `uis/backoffice/app/talent/` + `docs/archive/talent-pipeline-tracker-retirement.md` |
| Shared TypeScript code | `packages/shared/` |
| Shared incident contracts and CSV validation | `packages/trackflow_incidents/` |
| Non-code shared resources | `resources/` |
| Product AI agents | `agents/` |
| Data pipelines | `data/` |
| Workflow automations | `workflows/` |
| Product agent capabilities | `skills/` |
| Repo-wide scripts and utilities | `scripts/` |
| Container and deployment definitions | `docker/`, `compose.yaml`, `compose.coolify.yaml` |

## Where New Engagement Code Goes

- **Engagement 1** - delivered in `apps/marketing-site/`  
  Built; code retired June 2026. Surface lives at `uis/website/` — see `docs/archive/marketing-site-retirement.md`.

- **Engagement 2** - `packages/shared/`  
  Built.

- **Engagement 3** - delivered in `apps/talent-pipeline-tracker/`  
  Built; code retired June 2026. Now at `uis/backoffice/app/talent/` — see `docs/archive/talent-pipeline-tracker-retirement.md`.

- **Engagement 4** - `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/`  
  Built.

- **Engagement 5** - `services/central-api/`
  Built. Inventory, the Centralized Incident Manager, and the boundary-waived
  Supplier Directory use separate domains in this service. See
  `docs/briefs/05-backend-inventory-management.md`,
  `docs/planning/centralized-incident-manager.md`, and
  `docs/planning/supplier-directory-postgres-migration.md`.

- **Engagement 6** - Data Pipelines & Telemetry
  In progress. A `telemetry` domain in `services/central-api/` (table
  `telemetry_events`, exact metrics from `StockEntry`/`StockExit`, best-effort
  post-response diagnostics, enforced retention), Identity auth audit logs in
  `services/identity/`, and a Back Office Telemetry route in `uis/backoffice/`.
  A follow-on **live operations feed** makes the portfolio-production deployment
  feel live: `services/central-api/central_api/domains/operations/` (the
  `operations_feed_control` kill switch), `services/central-api/scripts/operations_feed.py`
  (single-writer worker) and `scripts/db_size_guard.py` (Supabase-Free bounding),
  plus `uis/backoffice/lib/hooks/useAutoRefresh.ts`, `components/OperationsOverview.tsx`
  (the new live landing), and the Engagement-2 scoring demo relocated to
  `/backoffice/carrier-scoring`. See `docs/briefs/06-data-pipelines-telemetry.md`,
  `docs/runbooks/operations-feed.md`, and the living signal reference
  `docs/runbooks/telemetry-inventory.md`.
  Production hardening lives in `data/pipelines/business_performance/worker.py`,
  `services/central-api/scripts/{maintenance_worker,production_migrate}.py`, the root Compose
  files, and `.github/workflows/deploy-production.yml`. The reporting remediation has
  independent claim renewal,
  token-guarded run/stage correlation, fail-closed orchestrator health, orphan reconciliation,
  a hard run watchdog, optional R2 recovery results, API-only retention, an isolated read-only
  database backup service, six server-derived operator states, and release startup guards.
  **The weekly business report is live in production**: the reporting worker and
  reconciled hourly/weekly rollup path are healthy, and the Back Office serves the first verified
  six-row snapshot. Phase 6.1 is deployed as immutable image
  `13bba2e` through revision `20260728_0011` and closed by a documented owner exception after the
  remaining controlled exercises were omitted. Phase 6.2 durable hourly SQL rollups are deployed
  through `20260728_0012` and owner-accepted after corrected publication and exact reconciliation.
  Phase 6.3 is deployed through additive revision `20260728_0013`; its reconciled cutover and
  control-plane/safe-stale drill passed. The owner accepted Phase 6.3 as-is by explicit exception
  on July 28 and approved beginning Phase 6.4; the computation-disable drill and seven-day
  production observation were waived, not passed or executed. Phase 6.4's 48-hour studies and
  seven-day clean run were also waived, not passed or executed. The
  production direct-SQL executor swap is separately owner-approved and prepared after same-day
  queue/recovery/parity/volume verification, with no resource-limit change. Deployment
  verification of that swap remains open. **Prefect was retired in August 2026** under owner
  approval — six orchestration containers, their dedicated database, the runtime dependency, and
  the R2 transformation cache are gone, and `direct_sql` is the only executor. See
  `docs/archive/prefect-orchestration-retirement.md`.
  **Stock is now materialized** in `stock_balances` (migration `20260820_0020`), maintained
  in-transaction under the existing SKU lock, with `scripts/verify_stock_balances.py` as the drift
  check. That decoupling is what permits **30-day movement-ledger retention**
  (`scripts/prune_movement_ledger.py`, FK-ordered and micro-batched), which replaced the separate
  26-week business-event prune — the `ON DELETE RESTRICT` keys into `stock_exits` make those two
  windows inseparable. Design and its `spec.md` §8.4 proof:
  `docs/design/movement-ledger-retention.md`.
  Independent Phases 6.5.a–b produced an
  owner-accepted offline Random Forest baseline and formal chronological evaluation. The evaluation
  diagnoses overfitting and unstable temporal validation, so it is not approved for operational use;
  6.5 is complete as an offline evaluation. The engagement is covered by two
  owner-approved specifications — `docs/planning/remaining_planning/spec.md` (Phases 6.1-6.4,
  reporting reliability) and `docs/planning/remaining_planning/spec-6.5-sales-forecasting.md`
  (6.5, runs in parallel).

- **Engagement 7** - RAG Knowledge Base
  Complete — merged to `main` and **deployed to production on 2026-08-17**: `RAG_ENABLED` with provider keys and
  a provisioned Qdrant indexed via `rag-index`; it grounds the Engagement 9 RFP Desk and powers the
  agent Ask-AI. A salesperson-voiced knowledge assistant over four policy documents in
  `docs/company-knowledge-base/`. Pure chunking in `data/process/rag.py`; the four functions
  `setup`/`embed`/`retrieve`/`query` in `data/pipelines/rag.py` (no orchestration framework). Vector
  store is self-hosted **Qdrant** (collection `trackflow`, 1536-dim cosine, added to `compose.yaml`
  and `compose.coolify.yaml`). Embeddings: OpenAI `text-embedding-3-small`; generation: DeepSeek
  `deepseek-chat`. Endpoint `POST /knowledge/query` lives in the new
  `services/central-api/central_api/domains/rag/` domain and imports `query()` (no logic duplicated);
  it returns `503` unless `RAG_ENABLED=true` and both provider keys are set. Indexing CLI
  `rag-index` and eval harness `rag-eval` under `services/central-api/scripts/`; eval set at
  `data/eval/rag/test-queries.json`. The Back Office (`uis/backoffice/`) was refactored: home Ask-AI query
  box (`components/knowledge/AskKnowledgeBox.tsx`), a category-grouped sidebar
  (`lib/backoffice/navigation.ts`), a top-center Business ↔ Technical/Agent-OS toggle
  (`components/ViewToggle.tsx` + `lib/backoffice/view-context.tsx`), a header account menu
  (`components/account/AccountMenu.tsx`), dark mode (`lib/theme/context.tsx`), and an Agent-OS
  placeholder (`app/(protected)/agent-os/`). Design: `docs/rag/rag-design.md`; plan + beginner guide
  in `docs/planning/remaining_planning/07_rag_knowledge_base/`. Still open: provider keys, a
  provisioned Qdrant, and running `rag-index` + `rag-eval` against live services.

- **Engagement 8** - Agent Engineering (LangGraph)
  Stakeholder brief: `docs/briefs/08-agent-engineering.md`. The graph and safe Postgres trace store
  live in the Central API `agents` domain; the reusable OAuth-protected tool boundary lives under
  `mcps/`; Identity owns OAuth issuance and user jurisdiction. Phase 4 guardrails, Phase 5
  human-confirmed structured memory, and Phase 6 self-hosted Agent OS observability extend the same
  graph. The owner accepted Phases 0–6 and closed Engagement 8 on August 3, 2026. Agent OS lives in
  `uis/backoffice/`. The accepted local MCP/Inspector evidence is recorded in
  `docs/agents/mcp-owner-review-evidence-2026-08-03.md`; the Codespaces-specific exercise was waived
  at closeout and was not executed or passed.

- **Engagement 9** - Agentic Workflows: Automated RFP Desk (LangGraph)
  Stakeholder brief: `docs/briefs/09-agentic-workflows.md`. Owner-approved spec; **complete** —
  merged to `main` and deployed to production on 2026-08-17 (RFP Desk + agent Ask-AI live and
  verified). Delivered in phases on branch `engagement-9-agentic-workflows` with an owner pause after each. A multi-agent
  LangGraph workflow (intake & routing → per-department generation & self-evaluation → human approval
  → final document) in the new Central API `rfp` domain
  (`services/central-api/central_api/domains/rfp/`), with a "ticket mode" RFP Desk in
  `uis/backoffice/`. Reuses Engagement 7 `retrieve()`/`generate_answer()` and the Engagement 8
  guardrails and trace store. **Phase 0 (scaffolding)** adds the `rfp` domain (owner-scoped ticket
  reads, `503` until `RFP_ENABLED`), the durable `rfp_tickets` / `rfp_department_sections` /
  `rfp_final_documents` schema (migration `20260805_0017`), vetted deps `pdfminer.six` and
  `langgraph-checkpoint-postgres`, and three seed RFP documents in `data/raw/`. **Phase 1 (intake &
  routing)** adds multipart `POST /rfp/tickets` upload, `pdfminer.six` PDF→Markdown (Markdown kept,
  bytes dropped), a deterministic readability module, and a LangGraph classifier →
  orchestrator-worker-synthesizer intake graph (`domains/rfp/{document,readability,agents,graph,
  intake}.py`) that discards non-RFPs and routes valid ones to departments with a safe trace reusing
  the Eng 8 trace store, plus the Back Office RFP Desk at `/agent-os/rfp`. **Phase 2 (response
  generation)** adds a per-department DeepSeek generator (reusing Eng 7 `generate_answer`) and three
  deterministic evaluators (`domains/rfp/{evaluators,generation}.py`) — readability, relevance, §5
  compliance — in a generator-evaluator loop with a hard iteration cap, chained after routing so the
  ticket advances to `under_evaluation`. **Phase 3 (human approval & completion)** gives each active
  department its own interruptible approval graph (`domains/rfp/{approval,checkpointer}.py`) on a
  durable Postgres LangGraph checkpointer, keyed by a per-department `thread_id` so a native
  `interrupt()` pauses only that branch; a validated approve/reject/request_changes decision
  (`POST /rfp/tickets/{id}/departments/{dept}/decision`) resumes from the interruption, request_changes
  redrafts (capped), and once all sections approve an arbitration step consolidates the final document
  (`GET /rfp/tickets/{id}/document`) and the ticket reaches `done`. The checkpointer's tables are
  managed by its own `setup()` and excluded from `alembic check` in `migrations/env.py`. Currency
  (USD/EUR) derives from the RFP's client country; raw PDF bytes are never persisted. This is
  LangGraph work, not n8n. **Post-implementation hardening (merged to `main` and deployed to production 2026-08-17):**
  RFP drafts are grounded via a drafting-oriented DeepSeek prompt over `retrieve()` (new
  `pipelines.rag.complete()` primitive) instead of the refusing knowledge-assistant generator; the
  RAG Ask-AI endpoint no longer 500s on provider/vector faults (typed 502); the home Ask-AI box routes
  through the Engagement 8 agent (`POST /agent/query`) after fixing an OBO token-exchange bug (the
  router passed the whole `extract_access_token()` tuple, not the token); Agent OS records real
  DeepSeek generation tokens and MCP tool-call rows; placeholder "coming soon"/"Engagement N" UI copy
  was removed; and `AGENTS_ENABLED`/`RFP_ENABLED` are wired (off by default) into
  `compose.coolify.yaml`. Agent/MCP production exposure was owner-approved and deployed to production on 2026-08-17 (Engagement 8 decision).

- **Engagement 10** - Real-Time Systems: SSE Notifications and WebSocket Chat.
  Stakeholder brief: `docs/briefs/10-realtime-systems.md`; binding owner-approved specification:
  `docs/planning/remaining_planning/spec-10-realtime.md`. Phase 0 verified Coolify 4.3.6 custom-label
  merge and the same-origin priority `/realtime` route without changing production. Phases 1–2
  merged to `main` through PR #35: a bounded in-process bus,
  cookie-authenticated owner-only RFP SSE, immediate post-commit/pre-intake notification, and an RFP
  Desk stream client with buffered authoritative recovery and no polling. Phases 3–5 merged to `main`
  through PR #36 under `services/central-api/central_api/domains/chat/`: additive
  `chat_sessions`/`chat_messages`, owner-only bounded reads, concurrent-safe message ordering, daily
  90-day retention, the approved telemetry exception, authenticated HTTP session history, and a
  responsive chat slide-over with multi-turn IDs and route selection. The same-origin WebSocket adds
  guarded provider token deltas, a single producer per session, true provider-stream interruption,
  partial-message persistence, redirected turns, and authoritative reconnect snapshots. The owner
  accepted the implementation as complete on 2026-08-18. Phase 6 production rollout and feature
  enablement are deferred; the feature remains off by default and production is unchanged.

- **Final polish pass** - `docs/planning/remaining_planning/spec-11-final-polish.md`
  Corrective/presentational pass across delivered surfaces (branch `feature/final-polish-spec-11`).
  Website: header hamburger dropdown replaces the bottom `MobileNav`; the hero is a looping muted
  background video with a reduced-motion still fallback. Back Office: Agent OS telemetry is now
  produced end-to-end (RFP token/cost accounting, restored output previews under
  `AGENTS_STORE_CONTENT`); a new RFP final-document Markdown download route
  (`domains/rfp/render.py` + `GET /rfp/tickets/{id}/document/download`); Business Reporting manual
  trigger controls removed (product/demo decision) and inline-SVG charts
  added; "Ask AI" opens the relocated chat panel (`components/knowledge/ChatPanel.tsx` +
  `lib/chat/panel-context.tsx`) from any route; the top Business/Technical view toggle and
  `TechnicalOverview` were removed.

- **Engagement 11+** - planned from `docs/planning/remaining_planning/`.
  Read its `README.md` before planning or implementing: it holds the index, the sequence, and the
  precedence rule between owner-approved specifications and bootcamp planning inputs (which are
  requirements, not architecture). A project there with no approved specification is not ready to
  implement — produce analysis and a proposed spec, then stop for owner approval.

## Coding-Agent Infrastructure Vs. Product Agents

For the `.agents/` vs `agents/` vs `skills/` distinction, see the canonical table in `AGENTS.md`.

## Claude Notes

- Prefer `rg` and `rg --files` for searches.
- Before public-facing UI work, apply `.agents/rules/public-ui-visibility.md` and follow its linked `docs/standards/visibility.md`.
- Before auth, session, token, cookie, authorization, or AI-agent user-context work, apply `.agents/rules/authentication-security.md` and follow its linked `docs/standards/authentication-security-standard.md`.
- Before database or persistent-storage design, queries, schemas, repositories, migrations, seeds, recovery, or operations, apply `.agents/rules/database-engineering.md` and follow its linked `docs/standards/database-engineering-standard.md`.
- Before telemetry design or instrumentation (events, metrics, traces, correlation IDs, audit/security telemetry, analytics, retention, or AI telemetry), apply `.agents/rules/telemetry.md` and follow its linked `docs/standards/telemetry-standard.md`.
- Before adding or changing behavior in code, APIs, validation, failure paths, logging, or CI/deploy config, apply `.agents/rules/testing-error-handling-ci.md` and follow the relevant linked engineering-quality standard in `docs/standards/` (testing, error-handling, observability, production-readiness).
- Before adding, upgrading, or removing a dependency, third-party service, or AI model/provider, apply `.agents/rules/compliance-licensing.md` and follow its linked `docs/standards/compliance-licensing-standard.md`.
- Empty folders with READMEs are intentional scaffolding for future engagements.
