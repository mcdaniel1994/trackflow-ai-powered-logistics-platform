# TrackFlow

An AI-powered platform for last-mile delivery and warehouse management.

🌐 **Live demo:** [trackflow-ai-powered-logistics-plat.vercel.app](https://trackflow-ai-powered-logistics-plat.vercel.app/)

TrackFlow is a logistics operator running warehouses in Los Angeles and Zaragoza, serving e-commerce brands across the United States and Spain. This repository is the engineering platform that powers the company — a growing monorepo of websites, APIs, AI agents, and data pipelines built to replace manual operations with reliable, automated systems.

---

## ✅ Current Status

**Engagement 4** delivered the AI-driven engineering infrastructure: persistent project memory in `memory-bank/`, the cross-agent operating guide in `AGENTS.md`, scoped coding-agent rules and the `start-engagement` skill under `.agents/`, the forward-looking Next.js + TypeScript UI workspace (`uis/website/`, `uis/backoffice/`), and the reserved `services/` boundary. See `AGENTS.md` for how `.agents/` (coding-agent infrastructure) differs from the customer-facing product agents in `agents/`.

**Engagement 5** is in progress: Backend Inventory Management is establishing the
FastAPI Central API, PostgreSQL inventory persistence, and exact `/inventory/...`
contract under `services/central-api/`.

Auth 1, Auth 2, and Auth 3 are implemented as authentication subprojects, not Engagement 5: `services/identity/` owns users, login, refresh sessions, RS256 signing, and password reset/account recovery; `packages/trackflow_auth/` provides verify-only helpers for domain APIs; and `uis/backoffice/` hosts the authenticated Back Office shell plus public forgot/reset-password pages through a same-origin BFF.

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

### 🚧 Engagement 5 — Backend Inventory Management *(in progress)*

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

## 🗺️ Roadmap

| Engagement | Focus | Status |
|----------|------|--------|
| 1 | Corporate website + lead capture | ✅ Delivered — now `uis/website/` (original app retired June 2026) |
| 2 | Inventory & carrier scoring (TypeScript) | ✅ Delivered |
| 3 | Talent Pipeline Tracker | ✅ Delivered — now `uis/backoffice/app/talent/` (standalone app retired June 2026) |
| 4 | AI-Driven Engineering Infrastructure | ✅ Delivered — `memory-bank/`, `.agents/`, `uis/`, `services/` |
| 5 | Backend Inventory Management (Central API) | 🚧 In progress |
| 6 | Data pipelines & telemetry | ⏳ Upcoming |
| 7 | RAG knowledge base & semantic search | ⏳ Upcoming |
| 8 | AI agents (product, customer-facing) | ⏳ Upcoming |
| 9 | Workflow automation (n8n) | ⏳ Upcoming |
| 10 | Real-time dashboards & alerts | ⏳ Upcoming |

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
│       └── app/incidents/         # Incident Report Processor UI (subproject)
│
├── services/                      # APIs and backend services
│   ├── identity/                  # Python/FastAPI identity service
│   ├── central-api/               # Engagement 5 FastAPI + PostgreSQL inventory service
│   └── incident-processor/        # Python/FastAPI incident analysis subproject (CLI + API)
│
├── packages/                      # Shared code libraries
│   ├── shared/                    # @repo/shared-types: types + utilities (Engagement 2)
│   └── trackflow_auth/            # Python verify-only auth helpers for backend services
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
├── workflows/                     # n8n automation workflows
│
├── docs/                          # Documentation
│   ├── briefs/                    # Stakeholder briefs (per engagement)
│   ├── planning/                  # Subproject specs & architecture proposals
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
| AI | RAG, LLM agents, semantic search |
| Automation | n8n workflows |
| Infra | npm workspaces, monorepo, GitHub Codespaces |

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
