# TrackFlow

An AI-powered platform for last-mile delivery and warehouse management.

🌐 **Live demo:** [trackflow-ai-powered-logistics-plat.vercel.app](https://trackflow-ai-powered-logistics-plat.vercel.app/)

🔐 **Production Back Office:** [backoffice.forgehub.cloud](https://backoffice.forgehub.cloud/) *(authentication required)*

TrackFlow is a logistics operator running warehouses in Los Angeles and Zaragoza, serving e-commerce brands across the United States and Spain. This repository is the engineering platform that powers the company — a growing monorepo of websites, APIs, AI agents, and data pipelines built to replace manual operations with reliable, automated systems.

---

## ✅ Current Status

**Engagement 4** delivered the AI-driven engineering infrastructure: persistent project memory in `memory-bank/`, the cross-agent operating guide in `AGENTS.md`, scoped coding-agent rules and the `start-engagement` skill under `.agents/`, the forward-looking Next.js + TypeScript UI workspace (`uis/website/`, `uis/backoffice/`), and the reserved `services/` boundary. See `AGENTS.md` for how `.agents/` (coding-agent infrastructure) differs from the customer-facing product agents in `agents/`.

**Engagement 5** delivered Backend Inventory Management: the FastAPI Central API,
PostgreSQL inventory persistence, and exact `/inventory/...` contract live under
`services/central-api/`.

Auth 1, Auth 2, and Auth 3 are implemented as authentication subprojects, not Engagement 5: `services/identity/` owns users, login, refresh sessions, RS256 signing, and password reset/account recovery; `packages/trackflow_auth/` provides verify-only helpers for domain APIs; and `uis/backoffice/` hosts the authenticated Back Office shell plus public forgot/reset-password pages through a same-origin BFF.

The Centralized Incident Manager is also delivered as a subproject: Central API
persists incidents and their lifecycle in PostgreSQL, while the authenticated
Back Office `/incidents` route provides registration, filtering, status updates,
and leadership summaries.

Separate local and Coolify Compose paths now package Identity, Central API, and
Back Office. The production stack is verified on Coolify at
`backoffice.forgehub.cloud`; deployment, rollback, and remaining operational
gaps are documented in `docs/runbooks/`.

**Engagement 6** is in progress. Delivered and running in production: a Central API `telemetry`
domain with exact warehouse metrics, a live operations feed, always-on reporting and maintenance
workers, approval-gated migrations, dependency-aware readiness, automatic immutable-image rollback,
and a private, digest-pinned Prefect Server backed by its own PostgreSQL database.
`reporting.pipeline_runs` is the sole dispatch authority.

**The weekly business report is working in production.** As of July 28, 2026 the reporting worker,
Prefect, and reconciled hourly/weekly rollup path are healthy, and the authenticated Back Office
serves the first verified six-row weekly snapshot.
Two owner-approved specifications now cover the remaining work:
[`spec.md`](docs/planning/remaining_planning/spec.md) for reporting reliability (Phases 6.1–6.4) and
[`spec-6.5-sales-forecasting.md`](docs/planning/remaining_planning/spec-6.5-sales-forecasting.md)
for sales forecasting (6.5), which runs in parallel. The owner closed Phase 6.1 by explicit
exception after choosing to omit its remaining controlled exercises. Independent Phases 6.5.a and 6.5.b are complete
and owner-accepted as an offline evaluation: the formal chronological evaluation diagnoses
overfitting and does not approve the artifact for operational use. Phase 6.1 is deployed at
`13bba2e` / Alembic `20260728_0011`. Phase 6.2 schema/image is deployed through additive revision
`20260728_0012` and is owner-accepted after its corrected publication, exact reconciliation, and
runtime budget passed. Phase 6.3 is deployed through additive revision `20260728_0013`; its
reconciled cutover, first controlled run, and safe-stale rollback drill passed. On July 28, the
owner accepted Phase 6.3 as-is and approved beginning Phase 6.4 by explicit exception. The
computation-disable drill and required seven-day production observation were waived, not passed or
executed. The 6.5 offline artifact is not deployed.
Production soak, restore, outage,
memory-headroom, and rollback acceptance gates remain owner-approved external work.

---

## ❗ The Problem

TrackFlow reflects real-world logistics challenges:

- **Two warehouses, two systems**  
  Los Angeles and Zaragoza operate on separate systems with no shared inventory visibility.

- **Eight carriers, no unified data**  
  Carrier assignment is manual with no performance metrics (on-time rate, cost/kg, incidents).

- **Returns reviewed by hand**  
  18–25% of orders are returned and manually processed without consistent rules.

- **Customer support is all human**  
  80% of queries are repetitive and could be automated. No ticketing system or knowledge base.

- **No CRM**  
  Account managers rely on spreadsheets and email threads.

- **Manual reporting**  
  Weekly reports require hours of manual work every Sunday night.

---

## 🧠 What’s Been Built

### ✅ Engagement 1 — Corporate Website & B2B Lead Capture *(delivered)*

- Responsive marketing site (US + Spanish markets)
- Structured intake form for qualified leads
- Replaces vague, manual inquiry process

**Tech:**
- HTML5
- Tailwind CSS
- Vanilla JavaScript
- Schema.org structured data
- Full client-side validation

📁 Now served by: `uis/website/` — the original static app was retired June 2026 (`docs/archive/marketing-site-retirement.md`)

---

### ✅ Engagement 2 — Inventory & Carrier Scoring Engine *(delivered)*

- Inventory filtering by location and stock
- Carrier scoring (cost, speed, reliability)
- Shipping cost calculations
- Data validation before order processing

**Tech:**
- Strict TypeScript
- Pure functions (no mutations)
- Full interface modeling
- Edge case handling

📁 Location: `packages/shared/`

---

### ✅ Engagement 3 — Talent Pipeline Tracker *(delivered)*

- Candidate list for the Executive Assistant search
- Status and stage filtering
- Candidate detail, registration, editing, and notes

**Tech:**
- Next.js App Router
- TypeScript
- Tailwind CSS

📁 Now lives at: `uis/backoffice/app/talent/` — the standalone app was retired June 2026 (`docs/archive/talent-pipeline-tracker-retirement.md`)

---

### ✅ Engagement 4 — AI-Driven Engineering Infrastructure *(delivered)*

- Persistent project memory for coding agents (business, tech, progress)
- Root `AGENTS.md` operating guide with startup reading and pre-commit workflow
- Scoped coding-agent rules and a reusable `start-engagement` skill
- Forward-looking Next.js + TypeScript UI workspace (public website + internal backoffice)
- Backoffice view consumes the Engagement 2 logic via `@repo/shared-types`
- Reserved `services/` boundary for future APIs
- npm workspaces wired across `packages/*` and `uis/*` (originally also `apps/*`, retired June 2026)

**Tech:**
- Next.js App Router
- TypeScript
- Tailwind CSS
- npm workspaces

📁 Location: `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/`

---

### ✅ Engagement 5 — Backend Inventory Management *(delivered)*

- Unified SKU inventory across Los Angeles and Zaragoza
- Computed stock from immutable inbound and outbound movements
- Transaction-safe prevention of negative inventory
- Identity-issued token verification with Identity retaining TinyDB ownership

**Tech:**
- FastAPI
- SQLModel + PostgreSQL
- Alembic
- `trackflow_auth`

📁 Location: `services/central-api/`

---

### 🚧 Engagement 6 / 6.5 — Data, Telemetry & Forecasting *(in progress)*

- Production telemetry, live synthetic-but-canonical operations, and the durable weekly reporting
  queue remain in service; the weekly report now serves its first verified six-row snapshot.
- Phase 6.1 adds durable per-attempt failure evidence, separate liveness/core
  readiness/reporting verification, safe timeout ordering, and an owner-gated destructive reset.
- Phase 6.2 adds durable hourly SQL rollups, fixed cutoffs, trailing 72-hour recomputation, exact
  reconciliation, and 12-hour cadence; its production gate is accepted.
- Phase 6.3 adds atomic reconciled weekly activation, weekly/history plus hourly/current reads,
  transient-only inner retries, and explicit safe-503 or verified-stale rollback modes. It is
  deployed; rollback drill one passed. The owner accepted the phase by explicit exception and
  waived drill two and the seven-day observation without representing either gate as passed.
- Phase 6.4's 48-hour studies and seven-day clean run were waived by the owner, not passed or
  executed. The direct SQL executor passes same-day queue, recovery, parity, and 2× volume gates;
  its production swap is owner-approved and prepared for deployment without a resource-limit
  change. Deployment verification and separately approved final Prefect removal remain open.
- Independent Phase 6.5 adds the generated 2016–2025 revenue dataset, a fixed-seed strict-recursive
  offline Random Forest baseline, five-fold chronological evaluation, and versioned
  metrics/model/report/chart artifacts.
- The formal evaluation diagnoses overfitting and unstable temporal validation, so the artifact is
  explicitly not approved for serving or operational decisions. Engagement 6.5 is owner-accepted
  as a complete offline evaluation; Phase 6.1 is closed by documented owner exception, and Phase
  6.2 is production-accepted; 6.3 is owner-accepted by documented exception.

📁 Locations: `data/`, `services/central-api/`, `uis/backoffice/`, and `.github/workflows/`

---

### ✅ Centralized Incident Manager *(delivered subproject)*

- Browser-based incident registration across Central, Los Angeles, and Zaragoza
- Enforced open → in progress → resolved/discarded lifecycle
- Filters and aggregate metrics by status, category, origin, and branch
- Idempotent, privacy-safe import of the historical customer-service CSV

**Tech:** FastAPI, SQLModel, PostgreSQL, Alembic, Next.js, and shared Python validation

📁 Locations: `services/central-api/`, `packages/trackflow_incidents/`, and `uis/backoffice/`

---

### 🚢 Dockerization & Deployment Architecture *(deployed subproject)*

- Local Docker Compose stack for Identity, Central API, Back Office, and disposable PostgreSQL
- Separate Coolify Compose stack with private backends and explicit migration/seed profiles
- GitHub Actions builds Linux AMD64 images and publishes commit-pinned GHCR tags
  so the VPS only pulls and runs containers
- Supplier Directory folded into Central API with a privacy-preserving importer
- Backup, restore, migration, deployment, and rollback runbooks
- Production verification covers HTTPS, private backend networking, authentication,
  CSRF, password reset, PostgreSQL access, and approved inventory/supplier seeds

📁 Locations: `docker/`, `compose.yaml`, `compose.coolify.yaml`, and `docs/runbooks/`

Future production changes and the final Supplier Directory retirement remain approval-gated.

---

## 🗺️ Roadmap

| Engagement | Focus | Status |
|----------|------|--------|
| 1 | Corporate website + lead capture | ✅ Delivered — now `uis/website/` (original app retired June 2026) |
| 2 | Inventory & carrier scoring (TypeScript) | ✅ Delivered |
| 3 | Talent Pipeline Tracker | ✅ Delivered — now `uis/backoffice/app/talent/` (standalone app retired June 2026) |
| 4 | AI-Driven Engineering Infrastructure | ✅ Delivered — `memory-bank/`, `.agents/`, `uis/`, `services/` |
| 5 | Backend Inventory Management (Central API) | ✅ Delivered — `services/central-api/` |
| 6 | Data pipelines & telemetry | 🚧 Weekly reporting is live through `20260728_0013`; Phases 6.1 and 6.3 closed by owner exception, Phase 6.2 accepted; Phase 6.4 time gates waived and direct-SQL production swap approved/prepared, deployment verification pending |
| 6.5 | Sales forecasting (regression + evaluation) | ✅ Complete offline evaluation; owner accepted the overfitting diagnosis, model not approved for operational use |
| 7 | RAG knowledge base & semantic search | 🚧 Implemented on branch `engagement-7-rag-knowledge-base` (Qdrant + FastAPI `/knowledge/query` + Back Office Ask-AI refactor); pending owner review, provider keys, and Qdrant provisioning |
| 8 | AI agents (LangGraph, tools, MCP server, guardrails, memory) | ⏳ Planning inputs only — no spec yet |
| 9 | Agentic workflows — automated RFP desk (LangGraph) | ⏳ Planning inputs only — no spec yet |
| 10 | Real-time dashboards & alerts | ⛔ Blocked — no requirements document exists |

All remaining work is planned from
**[`docs/planning/remaining_planning/`](docs/planning/remaining_planning/)** — see its
[README](docs/planning/remaining_planning/README.md) for the index, sequence, and the precedence
rule between owner-approved specifications and bootcamp planning inputs.

---

## 🏗️ Repository Architecture

```text
trackflow/
├── AGENTS.md                      # Cross-agent operating guide (Engagement 4)
├── CLAUDE.md                      # Claude-specific orientation (Engagement 4)
├── README.md                      # This file
│
├── memory-bank/                   # Persistent project context for coding agents (Engagement 4)
│   ├── projectbrief.md            # Business, stakeholders, operational problems
│   ├── techContext.md             # Stack, architecture, decisions
│   └── progress.md                # Completed / active / planned engagements
│
├── .agents/                       # Coding-agent configuration (Engagement 4)
│   ├── rules/                     # Scoped development rules
│   └── skills/                    # Reusable repo-maintenance workflows
│       └── start-engagement/      # SKILL.md for spinning up a new engagement
│
├── uis/                           # UI workspace (Engagement 4) — sole home of TrackFlow UIs
│   ├── website/                   # Next.js + TS public site (Engagement 1 surface)
│   └── backoffice/                # Next.js + TS internal shell; consumes @repo/shared-types
│       ├── app/talent/            # Talent Pipeline Tracker (Engagement 3, migrated June 2026)
│       └── app/incidents/         # Centralized Incident Manager UI (subproject)
│
├── services/                      # APIs and backend services
│   ├── identity/                  # Python/FastAPI identity service
│   ├── central-api/               # PostgreSQL inventory + incident domains
│   └── supplier-directory/        # Temporary rollback copy pending cutover observation
│
├── packages/                      # Shared code libraries
│   ├── shared/                    # @repo/shared-types: types + utilities (Engagement 2)
│   ├── trackflow_auth/            # Python verify-only auth helpers for backend services
│   └── trackflow_incidents/       # Shared Python incident contracts and CSV validation
│
├── agents/                        # Product AI agents shipped to customers (Engagement 8)
│   ├── _template/                 # Starter pattern
│   └── tools/                     # Reusable agent tools
│
├── skills/                        # Reusable capabilities for product agents in agents/
│   ├── _template/                 # Starter pattern for new skills
│   ├── code-review/
│   ├── data-analysis/
│   └── research/
│
├── data/                          # Data engineering (Engagement 6)
│   ├── raw/                       # Source data
│   ├── process/                   # Cleaned data
│   ├── pipelines/                 # ETL logic
│   └── eval/                      # AI evaluation datasets
│
├── workflows/                     # Reserved for future automation workflows
│
├── docs/                          # Documentation
│   ├── briefs/                    # Stakeholder briefs (per engagement)
│   ├── planning/                  # Subproject specs & architecture proposals
│   │   └── remaining_planning/    # Entry point for all remaining work (specs + planning inputs)
│   ├── runbooks/                  # Operational runbooks
│   ├── standards/                 # Cross-cutting standards (visibility, etc.)
│   └── archive/                   # Historical planning artifacts
│
├── scripts/                       # Repo-wide utilities
└── resources/                     # Non-code shared resources
```


### Architectural Principles

- `uis/` may depend on `packages/`, never the reverse
- Types are first-class and shared across the system
- Meaningful top-level working directories include a README

---

## ⚙️ Tech Stack

| Layer | Tools |
|------|------|
| Frontend | HTML5, Tailwind CSS, vanilla JavaScript, React, Next.js App Router |
| Language | TypeScript, Python |
| Backend | Independent FastAPI services under `services/`; Central API uses SQLModel + PostgreSQL |
| Data | Prefect-orchestrated pipelines, Supabase PostgreSQL |
| AI *(planned)* | RAG with a vector store, LangGraph agents, MCP server, semantic search |
| Infra | npm workspaces, monorepo, Docker, GitHub Actions → GHCR, Coolify on a Hostinger VPS |

---

## 📌 About This Project

A long-running portfolio project built during the AI Engineering program at 4Geeks Academy. [![4Geeks Academy](https://img.shields.io/badge/AI%20Engineering-4Geeks%20Academy-orange)](https://4geeksacademy.com/)

Rather than isolated demos, TrackFlow is a **single, cohesive platform** for a realistic logistics company. Each engagement solves a real operational problem for a specific stakeholder and integrates into the growing system.

Built on the [4Geeks monorepo template](https://github.com/4GeeksAcademy/ai-engineering-company-project-monorepo), then significantly extended with custom architecture, business logic, and AI system design.

---

## 👋 About Me

**Cory McDaniel**  
AI Engineer — Dallas-Fort Worth, TX  

Former controls engineer. Now building AI systems that help small businesses save time through automation.

- [![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/corymcdanielai/) 
- 📧 corymcdaniel01@gmail.com  
- 📍 Dallas-Fort Worth, TX  

---

## 🎯 Availability

Open to AI engineering, automation, and applied AI roles — remote, contract, or sub-contract.
