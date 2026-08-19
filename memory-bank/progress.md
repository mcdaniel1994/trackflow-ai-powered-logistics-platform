# Progress

## Completed

- Engagement 1 - Corporate Website & B2B Lead Capture (`docs/briefs/01-website.md`): delivered in `apps/marketing-site/`; code retired June 2026, surface now served by `uis/website/` (see `docs/archive/marketing-site-retirement.md`).
- Engagement 2 - Inventory & Carrier Scoring Engine (`docs/briefs/02-inventory-carriers.md`): delivered in `packages/shared/`.
- Engagement 3 - Talent Pipeline Tracker (`docs/briefs/03-talent-pipeline-tracker.md`): delivered in `apps/talent-pipeline-tracker/`; code retired June 2026, now lives at `uis/backoffice/app/talent/` (see `docs/archive/talent-pipeline-tracker-retirement.md`).
- Engagement 4 - AI-Driven Engineering Infrastructure (`docs/briefs/04-ai-driven-engineering.md`): delivered in `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, and `services/`.
- Engagement 5 - Backend Inventory Management (`docs/briefs/05-backend-inventory-management.md`): delivered in `services/central-api/` with FastAPI, SQLModel, Alembic, PostgreSQL inventory movements, Identity token verification, idempotent seed data, and disposable-database tests.
- Engagement 8 - Agent Engineering (LangGraph) (`docs/briefs/08-agent-engineering.md`): Phases 0–6
  were accepted and the engagement was closed by the owner on August 3, 2026. Delivered scope
  includes the explicit LangGraph agent, OAuth-protected MCP boundary, jurisdiction-aware layered
  guardrails, confirmed structured memory, self-hosted Agent OS observability, safe routing-model
  token/cost accounting, and bounded trace retention. The owner accepted the disposable local
  MCP/Inspector evidence in `docs/agents/mcp-owner-review-evidence-2026-08-03.md` and waived the
  unexecuted Codespaces-specific exercise; the waiver is not a passing result. Production exposure
  and deployment remain separately owner-gated.
- Production deployment checkpoint (verified July 2, 2026 America/Chicago):
  Coolify serves the authenticated Back Office over HTTPS while Identity and
  Central API remain private; Supabase is migrated through `20260702_0003`,
  inventory and suppliers are seeded, and production incidents remain empty.

## Active

- Engagement 9 - Agentic Workflows: Automated RFP Desk (`docs/briefs/09-agentic-workflows.md`):
  complete — merged to `main` and deployed to production on 2026-08-17 (RFP Desk + agent Ask-AI live
  and verified); owner-approved spec, delivered in phases with an owner pause after each. A multi-agent
  LangGraph workflow (intake & routing → per-department
  generation & self-evaluation → human approval → final document) in the new Central API `rfp` domain,
  with a "ticket mode" RFP Desk in `uis/backoffice/`. Reuses Engagement 7 `retrieve()`/
  `generate_answer()` and the Engagement 8 guardrails and trace store; Phase 3 adds a durable Postgres
  LangGraph checkpointer with native `interrupt()` for branch-scoped human approval. **Phase 0
  (scaffolding) implemented:** the `rfp` domain (owner-scoped `GET /rfp/tickets[/{id}]`, `503` until
  `RFP_ENABLED`), migration `20260805_0017` (`rfp_tickets`, `rfp_department_sections`,
  `rfp_final_documents`), vetted deps `pdfminer.six` + `langgraph-checkpoint-postgres`, three seed RFP
  documents in `data/raw/`, and this brief. **Phase 1 (intake & routing) implemented:** multipart
  `POST /rfp/tickets` upload → `pdfminer.six` PDF→Markdown (Markdown persisted, raw bytes dropped) →
  deterministic readability → a LangGraph classifier → metadata extractor → orchestrator-worker-
  synthesizer graph (OpenAI structured output, mocked in CI) that discards non-RFPs and routes valid
  ones to their departments with a safe node trace reusing the Engagement 8 trace store; plus the
  Back Office RFP Desk (`/agent-os/rfp`, upload + live list/detail). Currency (USD/EUR) derives from
  the RFP's client country. **Phase 2 (response generation) implemented:** a per-department DeepSeek
  generator (reusing Engagement 7 `generate_answer`) drafts each section; three deterministic
  evaluators (readability, relevance, §5 compliance — currency/SLA/no-<48h-returns/discount-tier/
  no-carrier-rates) score it; a generator-evaluator loop with a hard iteration cap redrafts failures
  and leaves an unpassable section for a human rather than looping forever. Generation chains straight
  after routing, moving the ticket to `under_evaluation`. **Phase 3 (human approval & completion)
  implemented:** each active department has its own interruptible approval graph on a durable Postgres
  LangGraph checkpointer (`langgraph-checkpoint-postgres`), keyed by a per-department `thread_id` so a
  native `interrupt()` pauses only that branch while others proceed; resuming with a validated
  approve/reject/request_changes decision continues from the interruption, `request_changes` redrafts
  (capped) and re-interrupts, and once every section is approved an explicit arbitration step
  consolidates the final document and the ticket reaches `done`. New endpoints
  `POST /rfp/tickets/{id}/departments/{dept}/decision` and `GET /rfp/tickets/{id}/document`, plus RFP
  Desk approval controls and a completion banner. The checkpointer's tables are managed by its own
  `setup()` and excluded from `alembic check`. Engagement 9 implementation is complete across all four
  phases (0–3); pending owner review.
  **Post-implementation hardening pass (verified locally end-to-end, gates green, not pushed or
  deployed):** (1) RFP section drafts are now grounded — a drafting-oriented DeepSeek prompt over
  `retrieve()` policy context replaced the reused knowledge-assistant generator, which had refused
  ("I don't have that information documented"); live Luna (US/USD) and Zaragoza (ES/EUR) runs now pass
  all deterministic evaluators on the first iteration. A new low-level `pipelines.rag.complete()`
  primitive keeps the DeepSeek plumbing shared while letting the RFP writer supply its own system
  prompt. (2) Cross-cutting fixes on the same branch: the RAG Ask-AI `POST /knowledge/query` no longer
  500s on a vector-store/provider fault (wrapped as a typed 502); the home Ask-AI box now orchestrates
  through the Engagement 8 agent (`POST /agent/query`, RAG vs live ticket-status; RFP stays on its own
  desk) after fixing an OBO bug where the router passed the whole `extract_access_token()` tuple as the
  delegated token, breaking every MCP tool call; Agent OS now records real DeepSeek generation
  token counts (routing tokens already worked) and real MCP tool-call rows; and user-facing
  "coming soon"/"Engagement N" placeholder copy was removed from the Back Office. (3) Deploy wiring:
  `AGENTS_ENABLED` and `RFP_ENABLED` are declared (defaulted off) in `compose.coolify.yaml`; both
  Compose files validate and migration `20260805_0017` is in the `central-api-migrate` path. Enabling
  the agent/MCP path was owner-approved and deployed to production on 2026-08-17 (Engagement 8 decision).

- Engagement 7 - RAG Knowledge Base (`docs/briefs/07-rag-knowledge-base.md`):
  complete — merged to `main` and deployed to production on 2026-08-17 (`RAG_ENABLED` with provider
  keys and a provisioned Qdrant indexed via `rag-index`; grounds the RFP Desk and powers the agent).
  A salesperson-voiced assistant over the four policy documents in
  `docs/company-knowledge-base/`: pure semantic-section chunking (`data/process/rag.py`) and the four
  modular functions `setup`/`embed`/`retrieve`/`query` (`data/pipelines/rag.py`) written directly
  against the Qdrant and OpenAI SDKs (no orchestration framework). Vector store is self-hosted Qdrant
  (collection `trackflow`, 1536-dim cosine, deterministic uuid5 point IDs, added to both Compose
  files); embeddings use OpenAI `text-embedding-3-small`, generation uses DeepSeek `deepseek-chat`.
  `POST /knowledge/query` is a new `rag` domain in `services/central-api/` that imports `query()` and
  never returns raw chunks/scores; it stays `503` until `RAG_ENABLED=true` and both provider keys are
  set. 22 pipeline/chunking unit tests and 5 endpoint tests pass; 10-question eval set at
  `data/eval/rag/test-queries.json`. The Back Office was refactored (grouped sidebar, top-center
  Business ↔ Technical/Agent-OS toggle, header account menu, home Ask-AI box, dark mode, Agent-OS
  placeholder); all 126 frontend tests pass and the production build is clean. Design doc at
  `docs/rag/rag-design.md`. Open before go-live: provider keys, a provisioned Qdrant, and running
  `rag-index` + `rag-eval` (Recall@3 ≥ 80%, faithfulness) against live services.

- Engagement 6 - Data Pipelines & Telemetry (`docs/briefs/06-data-pipelines-telemetry.md`):
  in progress. Reporting-reliability Phase 6.1 is deployed as immutable image `13bba2e` through
  Alembic `20260728_0011` and closed by explicit owner exception after the remaining controlled
  exercises were omitted on 2026-07-28. Phase 6.2 additive revision `20260728_0012` is deployed
  and owner-accepted after its corrected 1,266-row publication, exact 12-dimension reconciliation,
  and 35.573-second durable attempt. Phase 6.3 is deployed through additive revision
  `20260728_0013`, with atomic reconciled weekly activation, hourly current-week reads,
  transient-only inner retries, computation-disable/verified-stale rollback modes, and operator
  status/UI. Its first controlled run published a verified six-row snapshot, and rollback drill one
  passed with safe 503, explicit stale serving, unrelated-route isolation, unchanged snapshot
  lineage, and no unexpected queue work. On 2026-07-28 the owner accepted Phase 6.3 as-is by
  explicit exception and approved beginning Phase 6.4. Rollback drill two and the required
  seven-day observation were waived by that decision; they were not passed or executed.
  Independent Phases 6.5.a–b are
  owner-accepted and complete as an offline
  evaluation: the relocated,
  deterministic 120-month generated dataset feeds an offline strict-recursive Random Forest
  baseline with versioned metrics/model/chart/report artifacts. Five chronological folds produce
  validation RMSE 50,273 ± 13,165 EUR and diagnose overfitting caused by bounded absolute-level
  extrapolation; the artifact is not approved for operational use.
  Phase 1 added a Central API `telemetry` domain with a `telemetry_events` table,
  exact warehouse metrics read from `StockEntry`/`StockExit`, best-effort post-response
  rejected-dispatch and `api.access.denied` diagnostics, Identity auth audit logs (logs only),
  enforced retention, bounded aggregates-only reporting endpoints, and a read-only Back Office
  Telemetry route (Fulfilment/Security). A follow-on **live operations feed** slice makes the
  portfolio-production Back Office feel live: a single-writer worker
  (`scripts/operations_feed.py`, pg advisory lock + `operations_feed_control` kill switch) writes
  real synthetic-but-canonical inventory movements ~every 5s so exact metrics stay live and
  reconcilable; dashboards auto-refresh ~5s without flicker (`lib/hooks/useAutoRefresh.ts`) and a
  new live **Operations Overview** replaces the static "Inventory + Carriers" landing (the
  Engagement-2 scoring demo moved to `/backoffice/carrier-scoring`). Production telemetry is now
  enabled with 7-day retention, a daily prune, and a `scripts/db_size_guard.py` size guard
  (400 MB soft / 450 MB hard, ledger-safe reset) that keeps Supabase Free bounded. Runbook:
  `docs/runbooks/operations-feed.md`; signal reference: `docs/runbooks/telemetry-inventory.md`.
  The dedicated-Prefect remediation has completed repository Phases 0-4 locally: a private digest-pinned Prefect
  3.7.8 Server stores orchestration state in its own PostgreSQL 16 volume, both reporting clients
  target it, and a release guard proves Prefect tables live in PostgreSQL rather than fallback
  SQLite. The worker now renews claims independently, records token-guarded Prefect run IDs and
  stages, fails closed on orchestrator health, reconciles orphaned runs, and has a hard execution
  watchdog with truthful readiness signals. `reporting.pipeline_runs` remains the sole dispatch
  authority. Optional transformation recovery results use a distinct R2 prefix, the maintenance
  worker prunes old terminal runs through the API only, and a pinned read-only backup service creates
  daily custom-format dumps with distinct `PREFECT_BACKUP_R2_*` credentials. The absent-R2 path and
  an isolated scratch restore are locally verified. The reporting API and Back Office now share six
  server-derived queue states, and the reporting worker's own fail-closed startup guard blocks it on
  SQLite fallback or incompatible server/client versions. The July 15 first production startup exposed
  Coolify translating PostgreSQL init-file bind mounts into directories; the hotfix now bakes those
  files into the pinned database image, repairs existing volumes through an idempotent one-shot
  bootstrap, and keeps Central API container liveness independent of reporting readiness. The hotfix
  redeployment then ended as Coolify exit 255 — the SSH command boundary, not a guard rejection
  (a real guard failure exits 1 in ~13s). `up -d` stays attached until every
  `service_completed_successfully` dependency exits, so gating the worker on the one-shot guards put
  them on the deploy critical path. The guards now report without gating startup, enforcement moved
  into the worker, guards emit fixed tokens, and `scripts/release/measure_compose_startup.sh` makes
  the attach time measurable (18s chain against ~3GB of per-deployment pulls). Approved
  redeployment is complete. The Phase 6.3 control-plane outage/restore drill passed; its
  computation-disable and seven-day gates were waived by owner exception. The owner also waived
  Phase 6.4's 48-hour steady-state/deployment/post-change studies and seven-day clean run, recording
  them as waived rather than passed or executed. The production direct-SQL executor swap is
  separately approved and prepared after same-day queue/recovery/parity/2×-volume verification,
  with no resource-limit change. Deployment verification is pending. Final Prefect topology
  removal remains separately approval-gated.
  The earlier production-hardening slice replaces manual reporting recovery and Coolify cron jobs with
  always-on reporting and maintenance workers, fixes Prefect failure propagation, exposes worker
  health, adds fail-closed migration/grant verification, introduces `/health/live` and
  `/health/ready`, and automatically restores the previous immutable image after deploy or
  readiness failure. The GitHub Production secret is configured; credential rotation remains an
  owner action. Rollback drill one is complete; the separate computation-disable drill was waived,
  not executed, under the Phase 6.3 owner exception.
  Browser analytics, a durable event queue, correlation IDs, metrics/tracing backends, real
  carriers tables, and AI telemetry remain explicitly deferred.

- Final polish pass (spec: `docs/planning/remaining_planning/spec-11-final-polish.md`) — a
  pre-recording corrective/presentational pass across delivered surfaces, on branch
  `feature/final-polish-spec-11`. **Phase 1 (public website):** the fixed bottom `MobileNav` was
  replaced by a header hamburger dropdown in `SiteHeader.tsx` (native `<button>`/`<nav>`, Escape/
  backdrop close, focus return), and the hero still image became a looping, muted, `playsInline`
  background video (`Hero.tsx` + `trackflow_video.mp4`) with a mandatory `prefers-reduced-motion`
  still fallback; both gradient overlays and the JSON-LD PNG are preserved. **Phase 2 (Back Office):**
  (2.1) Agent OS telemetry is now produced, not just rendered — RFP intake captures `usage_metadata`
  via `with_structured_output(include_raw=True)`, drafting uses a new `pipelines.rag.complete_with_usage`
  primitive, generation/approval steps carry summed tokens (cost `None` when unpriced via a shared
  `combine_usage`), approval latency sums step durations, and output previews return under owner-approved
  `AGENTS_STORE_CONTENT=true` (chat-session suppression removed, guardrail suppression kept); DeepSeek
  stays unpriced by design and the dashboard shows "Not priced". (2.2) The RFP final document is now
  reachable: a deterministic Markdown renderer (`domains/rfp/render.py`), a `GET
  /rfp/tickets/{id}/document/download` route, BFF allowlist + client `downloadRfpDocument`, and a
  `CompletedProposal` UI in the RFP Desk. (2.3) The Business Reporting Run now / Force refresh triggers
  were removed as a product/demo decision (not a Prefect consequence — Prefect is still deployed;
  the buttons drove real direct-SQL work) and replaced with hand-rolled inline-SVG charts (KPI tiles,
  grouped bars, discrepancy-rate bars, a 6-week trend line) on a validated palette, keeping the precise
  table. (2.4) "Ask AI" now opens the chat slide-over from any route: the Engagement 10 chat client was
  relocated verbatim into `components/knowledge/ChatPanel.tsx`, mounted once in the protected layout via
  `ChatPanelProvider`; opening issues no write. (2.5) The top Business/Technical toggle, its context, and
  the orphaned `TechnicalOverview` were deleted (owner chose deletion); the home always shows the live
  Operations Overview. All website and Back Office gates (type-check, lint, test, build) pass; Central
  API RFP/agents/rag tests pass with `.env` moved aside for CI parity.

## Subprojects

- Centralized Incident Manager (spec: `docs/planning/centralized-incident-manager.md`) — built; remains a subproject rather than a numbered engagement. Persistent PostgreSQL CRUD, lifecycle transitions, summary metrics, and historical seed support live in `services/central-api/`; shared privacy-safe legacy validation lives in `packages/trackflow_incidents/`; and the Back Office manager lives at `/incidents`.
- Incident Report Processor (spec: `docs/planning/incident-report-processor.md`) —
  retired July 2026 after its fixture and privacy-safe import dependency moved
  to Central API (`docs/archive/incident-report-processor-retirement.md`).
- Supplier Directory (spec: `docs/planning/supplier-directory.md`) — folded
  into Central API as a PostgreSQL domain with an idempotent TinyDB importer;
  list/detail responses still expose only `has_contact_email`. The standalone
  service and original TinyDB remain rollback assets until the production
  observation window closes.
- Auth 1 Backend Authentication and API Route Protection (spec: `docs/planning/auth/plans/auth-1-implementation-plan.md`) — built; explicitly **not** Engagement 5. Lives in `services/identity/` and `packages/trackflow_auth/`, and protects Central API plus the supplier-directory transition service.
- Auth 2 Back Office Authentication (spec: `docs/planning/auth/plans/auth-2-implementation-plan.md`) — built; explicitly **not** Engagement 5. Lives in `uis/backoffice/` with a same-origin BFF under `app/api/*`, protected Back Office views, login/logout, profile, change-password, admin user management, temporary-password first-login flow, CSRF forwarding, centralized `401` handling, and frontend tests.
- Auth 3 Password Reset and Account Recovery (spec: `docs/planning/auth/plans/auth-3-implementation-plan.md`) — built; explicitly **not** Engagement 5. Lives in `services/identity/` with hashed single-use TinyDB reset tokens and Resend email delivery, and in `uis/backoffice/` with public `/forgot-password` and `/reset-password` pages through the same-origin BFF.

## Migration Decisions

- June 2026 — Talent Pipeline Tracker migrated from `apps/talent-pipeline-tracker/` into `uis/backoffice/app/talent/` (routes `/talent`, `/talent/new`, `/talent/[id]`; env var renamed to `NEXT_PUBLIC_TALENT_API_URL`). The standalone app was deleted after the migration was verified (lint, type-check, build, route smoke tests).
- June 2026 — `apps/` retired entirely: `apps/marketing-site/` deleted after verifying `uis/website/` covers its surface page-for-page, and `packages/tailwind-config/` deleted with it (its only purpose was compiling the marketing site CSS). Retirement notes live in `docs/archive/`.

## Planned Next

All remaining work is planned from `docs/planning/remaining_planning/`. Its
`README.md` is the index, sequence, and precedence rule between owner-approved
specifications and bootcamp planning inputs — read it before planning or
implementing any of the items below.

- Engagement 6.1-6.4 - reporting reliability remediation. Owner-approved
  specification: `docs/planning/remaining_planning/spec.md`. Phase 6.1 is closed by documented
  owner exception. Phase 6.2 is production-accepted. Phase 6.3 is deployed through
  `20260728_0013`; controlled rollout steps 1-6 and rollback drill one passed. The owner accepted
  Phase 6.3 by explicit exception on 2026-07-28, waiving rollback drill two and the seven-day
  observation without executing them. Phase 6.4's time gates are likewise waived, not passed or
  executed. Its direct SQL executor, allowlisted selection, and same-day verification are complete;
  the production swap is approved/prepared, with deployment verification and separately approved
  final Prefect removal still open.
- Engagement 6.5 - sales forecasting. Owner-approved specification:
  `docs/planning/remaining_planning/spec-6.5-sales-forecasting.md`. Independent of
  6.1-6.4 and runs in parallel with it, not after. Phases 6.5.a–b are complete and owner-accepted
  as an offline evaluation; the overfitting model remains prohibited from operational use.
- Engagement 7 - RAG knowledge base and semantic search. Complete — merged to `main` and
  deployed to production on 2026-08-17 (see above).
- Engagement 9 - Agentic workflows for the RFP desk. Owner-approved spec; complete (see above).
  Merged to `main` and deployed to production on 2026-08-17 (RFP Desk + agent Ask-AI live). This is
  LangGraph work, not n8n; the earlier "workflow automation with n8n" framing does not match the
  assignment documents.
- Engagement 10 - Real-time systems. Owner-approved specification:
  `docs/planning/remaining_planning/spec-10-realtime.md`. Phase 0 read-only verification confirmed
  Coolify 4.3.6 preserves custom Traefik labels and that a priority-1000
  `Host(backoffice.forgehub.cloud) && PathPrefix(/realtime)` router can target private
  `central-api:8000`. Phases 1–2 merged to `main` through PR #35: bounded owner-scoped in-process
  fan-out, cookie-authenticated SSE with keep-alive and
  token-expiry close, post-commit/pre-intake `rfp_ticket_created` publication, and an RFP Desk
  `fetch`/`ReadableStream` client with buffered snapshot recovery, deduplication, jittered reconnect,
  and no list/detail polling. Phases 3–5 merged to `main` through PR #36 on 2026-08-18: additive
  `20260818_0018` chat session/message persistence, database-enforced ordering and
  invariants, owner-scoped bounded reads, 90-day cascade retention in the maintenance worker, and the
  approved raw-chat-history exception without relaxing trace/log exclusions; authenticated session
  history; a responsive chat slide-over with textarea reset, multi-turn IDs, and Auto/Knowledge
  base/Ticket lookup selection; and the same-origin cookie-authenticated chat WebSocket with guarded
  provider answer deltas, one active producer per session, genuine provider-stream abort,
  interrupted partial-message persistence, redirected turns, capped reconnect/backoff, and
  authoritative connect/reconnect snapshots. The owner accepted the Engagement 10 implementation
  as complete. Phase 6 production deployment, migration execution, feature enablement, live
  verification, and rollout/runbook closeout are deferred. `RFP_ENABLED` and `AGENTS_ENABLED` stay
  off by default; no production mutation occurred.
- Cross-cutting backlog (`important_considerations/others.md`): website
  contact-form lead persistence, a job-applicant form plus migration off the
  third-party talent API, and a Back Office information-architecture
  restructure. Fold each into the engagement that forces it rather than creating
  a new engagement number.
- Production restore drills and Supplier Directory retirement after its
  observation window.

## Open Decisions And Known Risks

- Lead-form persistence remains deferred and is not part of Engagement 5.
- Production-target release checks now gate GHCR image publishing, and eligible
  `main` builds proceed to an approval-gated, SHA-pinned Coolify deployment.
  The Coolify `4.1.2` and GitHub Production environment prerequisites are
  configured. Broad PR CI, browser E2E, and dependency/secret scanning remain
  follow-ups; the first live automated deployment exposed the documented Prefect startup defect,
  while the July 28 immutable deployment verified its hotfix and Phase 6.1. The owner omitted the
  remaining Phase 6.1 exercises. Phase 6.3 rollback drill one ran successfully; the owner later
  waived drill two and the seven-day observation and accepted the phase by explicit exception.
  The Phase 6.4 direct-SQL production swap and time-gate waivers are approved; deployment
  verification remains open, with resource-limit changes and final Prefect removal unapproved.
- Supabase Free and the Identity volume have no scheduled backups under the
  accepted disposable-data waiver; meaningful production data requires
  revisiting backup and restore requirements first.
- Junecoast tokens are duplicated across `uis/website/` and `uis/backoffice/`; promoting them into a shared package is a follow-up. (The third copy disappeared with the June 2026 retirement of `apps/talent-pipeline-tracker/`.)
