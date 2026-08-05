# Brief: Agentic Workflows — Automated RFP Desk

## Client: TrackFlow · Stakeholder: Miguel Torres (Commercial Director)

## Status

In progress — Engagement 9. Owner-approved specification exists (analysis + proposed spec accepted
before implementation). Delivered in phases with an owner review pause after each: **Phase 0
(scaffolding) is being implemented on branch `engagement-9-agentic-workflows`.** Phases 1–3 (intake &
routing, response generation, approval & completion) follow in order. This is LangGraph work, not
n8n. Nothing is deployed; production exposure remains owner-gated.

## Background

RFPs — requests for a logistics-outsourcing proposal — land on Miguel Torres's desk from e-commerce
brands (fashion, electronics, cosmetics) that want TrackFlow to run their warehousing, last mile,
returns, or some combination, in the United States, Spain, or both. Today each account manager builds
the proposal by hand, coordinating over email with three departments — Warehouse Operations (Ana
Whitfield), Last Mile & Carrier Management (Carlos Vega), and Reverse Logistics (Sofía Ramos). The
process takes days, and proposals sometimes arrive after the prospect has already signed with a
competitor.

This engagement builds on the platform's agent capabilities. Engagement 7 produced the RAG knowledge
base over TrackFlow's policy documents; Engagement 8 produced the secure LangGraph agent runtime,
OAuth-protected tools, jurisdiction-aware guardrails, human-confirmed memory, and the self-hosted
trace store. Engagement 9 reuses both: the RFP workflow is a *multi-agent* LangGraph graph that
grounds its drafts in the Engagement 7 retrieval/generation functions and runs behind the Engagement
8 guardrails and trace store.

## Stakeholder Request

> **Miguel Torres, Commercial Director:** "Every week we get dozens of RFPs as PDFs, and putting a
> proposal together is still a manual relay between Warehouse, Last Mile, and Reverse Logistics.
> Nobody can tell just from reading the document who needs to be asked what. I want to upload an RFP
> and watch a ticket move through the stages — is this even a real RFP, what does each department
> need to answer, draft each section, check it against our own rules, and then let a human from each
> department sign off before anything goes to the client. It has to feel like one continuous process,
> from upload to a finished document, in under two days instead of several."

The tech lead's three tickets frame the work: (1) intake and routing, (2) response generation and
self-evaluation, (3) human approval and final-document completion.

## Assignment

Build a phased, multi-agent LangGraph workflow in a new `rfp` domain of the Central API
(`services/central-api/central_api/domains/rfp/`), with a "ticket mode" RFP Desk in the Back Office
(`uis/backoffice`). Reuse the Engagement 8 runtime primitives (guardrails, trace store, RagConfig)
and the Engagement 7 `retrieve()` / `generate_answer()` functions. Persist ticket state, department
sections, and final documents in PostgreSQL with Alembic migrations. Use a durable Postgres
LangGraph checkpointer so the Part 3 human-approval interrupt can pause one department's branch,
persist, and resume exactly where it left off without blocking other departments.

## What You're Building

### Departments and data (from the assignment context)

Exactly three department identifiers: `warehouse` (Ana Whitfield — storage capacity, cost per
pallet/SKU, onboarding time), `lastmile` (Carlos Vega — cost per shipment, carriers by destination,
delivery SLA), and `reverse` (Sofía Ramos — returns cost and turnaround, only when requested). Not
every RFP needs all three; the orchestrator decides from the requested scope.

Ticket statuses: `analyzing`, `waiting_for_approval`, `drafting`, `under_evaluation`, `done`,
`discarded`. Currency is derived from the RFP's `client_country`: **USD for US, EUR for Spain** — from
the document, never from user input.

### Phase 0 — Scaffolding (this phase)

- New `rfp` domain package (models, schemas, config gate, repository, service, router) registered in
  the app; owner-scoped `GET /rfp/tickets` and `GET /rfp/tickets/{id}` reads, `503` when the feature
  flag `RFP_ENABLED` is off (mirroring the RAG domain gate).
- Durable schema in one Alembic migration: `rfp_tickets`, `rfp_department_sections`,
  `rfp_final_documents`, with CHECK constraints on every status/country/currency vocabulary.
  Node-level traceability reuses the Engagement 8 agent trace store rather than a parallel table.
- Vetted, locked dependencies: `pdfminer.six` (PDF text) and `langgraph-checkpoint-postgres` (durable
  checkpointer). `markitdown[pdf]` was rejected to avoid ~179 MB of unneeded native ML runtime;
  readability uses a deterministic in-repo module instead of `py-readability-metrics`/`nltk` (which
  fails offline). `THIRD_PARTY_LICENSES.md` records the additions.
- Three seed RFP documents in `data/raw/` and a stakeholder brief (this document).

### Phase 1 — Intake & Routing

Multipart PDF upload creates a ticket; convert PDF→Markdown on upload and **persist only the Markdown
plus safe metadata — never the raw PDF bytes**. A classifier agent decides whether the document is a
legitimate RFP; a non-RFP stops the flow in an explicit `discarded` state (never silent). Extract
safe metadata (client, country, requested services, volume, deadline, budget) and a deterministic
readability grade. An orchestrator-worker-synthesizer pattern (separate agents, not a monolith)
determines which departments apply and produces, per department, the key aspects Sales must request.

### Phase 2 — Response Generation

A generator agent per active department drafts its section, grounded in the Engagement 7 knowledge
base. Three evaluators run in parallel per section: readability, relevance, and **deterministic
compliance** against the guidelines (currency matches `client_country`; on-time delivery SLA % is
stated; no returns processing promised under 48 hours; a volume-based discount-tier table is present;
no negotiated carrier rates are disclosed). Failing sections return to their generator with concrete
feedback under a hard iteration cap; a section that cannot pass is surfaced for a human, not looped
forever. Ticket reflects `drafting` and `under_evaluation`.

### Phase 3 — Approval & Completion

A native LangGraph `interrupt()` per department pauses only that department's branch, persists state
to the Postgres checkpointer, and resumes from the interruption on a validated human decision
(`approve` / `reject` / `request_changes`) — other ready departments keep moving. An explicit
arbitration node (capped) resolves contradictions between departments. Once every active department
has approved, a synthesizer generates the final document (correct currency). Every node execution is
recorded with agent, safe input/output summary, and timestamp for full traceability. The RFP Desk
gains per-department approval controls.

### Back Office RFP Desk (`uis/backoffice`)

`app/(protected)/agent-os/rfp/` with a `RfpDesk` component (list + live detail, reusing
`useAutoRefresh` and the Agent OS dashboard patterns), a same-origin BFF allowlist under
`app/api/rfp/`, a typed client, a PDF upload control, and per-department approval buttons.

### Jurisdiction vs. client_country

Operator jurisdiction stays server-derived from the authenticated user (Engagement 8) and governs
authorization and guardrail isolation. `client_country` is untrusted data extracted from the
document, validated against `{US, ES}`; it drives currency and which policy corpus grounds the
compliance evaluator, but never overrides authorization, and a ticket is pinned to one country so US
and Spain policy cannot mix.

## Acceptance Criteria

- A ticket accurately reflects the real flow status at every moment (`analyzing`,
  `waiting_for_approval`, `drafting`, `under_evaluation`, `done`, `discarded`).
- Non-RFP documents are rejected into `discarded` without stopping the rest of the system.
- Metadata and a readability metric are computed and stored for every processed document; raw PDF
  bytes are never persisted.
- The orchestrator-worker-synthesizer and generator-evaluator patterns are implemented as separate
  agents, with a verifiable iteration cap and explicit arbitration node.
- Human approval is a real in-graph `interrupt()` with a durable Postgres checkpointer: it pauses only
  the waiting department's branch, persists state, and resumes without restarting the whole flow.
- The final document is generated only after every active department approves, in the correct
  currency, with no cross-country policy mixing.
- Every node execution is traceable (agent, safe summary, timestamp); no prompts, tool arguments,
  addresses, warehouse routes, negotiated carrier rates, or raw retrieved passages are logged or
  persisted (telemetry standard §8).
- Unit tests cover the classifier, at least one worker, at least one generator and evaluator
  (including a failing evaluation), interrupt/resume, the iteration cap, and arbitration; all provider
  and PDF-conversion calls are mocked. Central-api release gates pass against real PostgreSQL.

## Out of Scope

- Any production deployment, exposure, or provider spend (all mocked in CI; owner-gated in prod).
- n8n or any non-LangGraph workflow engine.
- Retaining original RFP PDFs, or storing exact addresses, warehouse routes, or negotiated carrier
  rates in any table.
- Engagement 10 (real-time dashboards) and unrelated cross-cutting backlog items.
