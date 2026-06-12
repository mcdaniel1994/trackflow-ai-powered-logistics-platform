# Technical Context

## Current Stack

- `packages/shared/` - delivered Engagement 2 strict TypeScript domain types and pure utilities for inventory, carrier scoring, shipping costs, reporting, search, and validation.
- `uis/website/` - public Next.js + TypeScript website (Engagement 4); sole home of the Engagement 1 marketing surface since the static `apps/marketing-site/` was retired in June 2026.
- `uis/backoffice/` - internal Next.js + TypeScript shell (Engagement 4) that consumes Engagement 2 logic; hosts the Talent Pipeline Tracker at `/talent` (Engagement 3, migrated June 2026) and the Incident Report Processor UI at `/incidents`.
- `services/incident-processor/` - Python/FastAPI subproject (CLI + API + analysis core) for CX incident exports; intentionally outside the npm workspaces.

## Repository Architecture

```text
trackflow/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── memory-bank/
├── .agents/
├── uis/
│   ├── website/
│   └── backoffice/
├── packages/
│   └── shared/
├── services/
│   └── incident-processor/
├── agents/
├── skills/
├── data/
├── workflows/
├── scripts/
├── resources/
└── docs/
```

## Delivered Engagements

- Engagement 1 - Corporate Website & B2B Lead Capture: delivered in `apps/marketing-site/`; code retired June 2026, surface now at `uis/website/` (`docs/archive/marketing-site-retirement.md`)
- Engagement 2 - Inventory & Carrier Scoring Engine: `packages/shared/`
- Engagement 3 - Talent Pipeline Tracker: delivered in `apps/talent-pipeline-tracker/`; code retired June 2026, now at `uis/backoffice/app/talent/` (`docs/archive/talent-pipeline-tracker-retirement.md`)
- Engagement 4 - AI-Driven Engineering Infrastructure: `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/`, and npm workspace wiring

## Architectural Decisions

- `uis/` may depend on `packages/`; `packages/` must never depend on applications.
- `apps/` was retired in June 2026: active UI work lives in `uis/`, and retired delivered code is preserved via `docs/archive/` retirement notes plus git history, not on-disk copies.
- `uis/` is the sole UI workspace for public and internal Next.js + TypeScript interfaces.
- `services/` hosts backend services. `services/incident-processor/` (Python/FastAPI) is the first; it is intentionally not an npm workspace member. `services/central-api/` remains reserved for Engagement 5.
- npm workspaces are wired for `packages/*` and `uis/*`.
- `packages/shared` is consumed in this repo as `@repo/shared-types`; `uis/backoffice/` is the first workspace consumer.
- `packages/shared` exposes TypeScript source directly. Next.js consumers transpile it with `transpilePackages`; future plain Node services may need a build step or service-side transpilation.
- Public pages must comply with `docs/standards/visibility.md` sections 1-6 before merge.
- Junecoast is the active visual palette across current TrackFlow UIs.

## Folder Boundaries

- `memory-bank/`, `AGENTS.md`, and `.agents/` are coding-agent infrastructure for maintaining this repository.
- `agents/` and `skills/` are product architecture for future TrackFlow AI agents and their reusable business capabilities.
- `data/` is for future raw data, processed data, pipelines, and evaluation datasets.
- `workflows/` is for future n8n automation workflows.
- `resources/` is for non-code shared resources such as schemas, templates, and configuration assets.
