# `docs/briefs/`

Stakeholder briefs — the source of truth for what each engagement must deliver.

Each brief is owned by an internal stakeholder and frames the problem, scope, and acceptance criteria. Filenames use a numeric prefix matching the engagement number.

## Index

| # | Brief | Stakeholder | Status | Delivered Code |
|---|---|---|---|---|
| 01 | [Corporate Website & Lead Capture](01-website.md) | Marketing | ✅ Delivered | `uis/website/` (original `apps/marketing-site/` retired June 2026 — [retirement note](../archive/marketing-site-retirement.md)) |
| 02 | [Inventory & Carrier Scoring Engine](02-inventory-carriers.md) | Ana Whitfield, Head of Warehouse Operations | ✅ Delivered | `packages/shared/` |
| 03 | [Talent Pipeline Tracker](03-talent-pipeline-tracker.md) | Ana Whitfield, Head of Warehouse Operations | ✅ Delivered | `uis/backoffice/app/talent/` (original `apps/talent-pipeline-tracker/` retired June 2026 — [retirement note](../archive/talent-pipeline-tracker-retirement.md)) |
| 04 | [AI-Driven Engineering Infrastructure](04-ai-driven-engineering.md) | Andrés Kim, CTO | ✅ Delivered | `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/` |
| 05 | [Backend Inventory Management](05-backend-inventory-management.md) | Andrés Kim, CTO | ✅ Delivered | `services/central-api/` |
| 06 | [Data Pipelines & Telemetry](06-data-pipelines-telemetry.md) | Andrés Kim, CTO | 🚧 6.1 closed by owner exception; 6.2 production-accepted; 6.3 owner-accepted by exception; 6.4 time gates waived and direct-SQL production swap approved/prepared, deployment verification pending; independent 6.5.a–b complete offline | `data/`, `services/central-api/`, `services/identity/`, `uis/backoffice/`, `.github/workflows/` |
| 07 | [RAG Knowledge Base](07-rag-knowledge-base.md) | Miguel Torres, Commercial Director | ✅ Complete — merged to `main` and deployed to production (2026-08-17); `RAG_ENABLED` with provider keys and a provisioned Qdrant (indexed via `rag-index`); grounds the RFP Desk and powers the agent Ask-AI | `docs/company-knowledge-base/`, `data/`, `services/central-api/`, `uis/backoffice/`, `docs/rag/` |
| 08 | [Agent Engineering (LangGraph)](08-agent-engineering.md) | Valentina Cruz, Customer Experience Manager | ✅ Complete — Phases 0–6 owner-accepted August 3, 2026; local MCP/Inspector evidence accepted, unexecuted Codespaces-specific exercise waived (not passed) | `services/central-api/`, `services/identity/`, `packages/trackflow_auth/`, `mcps/`, `uis/backoffice/`, `docs/agents/` |
| 09 | [Agentic Workflows — Automated RFP Desk](09-agentic-workflows.md) | Miguel Torres, Commercial Director | ✅ Complete — all phases (0–3) merged to `main` and deployed to production (2026-08-17): intake & routing; generation & evaluation; interrupt-based human approval + final document. RFP Desk + agent Ask-AI live and verified | `services/central-api/`, `uis/backoffice/`, `data/raw/` |
| 10 | [Real-Time Systems — Push Notifications and Streaming Chat](10-realtime-systems.md) | Miguel Torres, Commercial Director; Valentina Cruz, Customer Experience | 🚧 Part 1 merged through PR #35; Phases 3–5 persistent WebSocket chat implemented on `feature/websocket-chat`, awaiting owner review | `services/central-api/central_api/domains/{realtime,chat}/`, `data/pipelines/rag.py`, `uis/backoffice/`, `compose.coolify.yaml` |

## Conventions

- Filenames: `NN-short-slug.md`
- Each brief opens with a one-line stakeholder identification and a Status section.
- Briefs are stakeholder voice — do not rewrite for uniformity once delivered.
