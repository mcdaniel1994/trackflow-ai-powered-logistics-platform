# Technical Context

## Current Stack

- `apps/marketing-site/` - delivered Engagement 1 static public site built with HTML, Tailwind CSS output, and vanilla JavaScript.
- `packages/shared/` - delivered Engagement 2 strict TypeScript domain types and pure utilities for inventory, carrier scoring, shipping costs, reporting, search, and validation.
- `apps/talent-pipeline-tracker/` - delivered Engagement 3 recruiting app built with Next.js App Router, TypeScript, and Tailwind CSS.
- `uis/website/` - Engagement 4 public Next.js + TypeScript website that refactors the Engagement 1 surface into reusable components.
- `uis/backoffice/` - Engagement 4 internal Next.js + TypeScript shell that consumes Engagement 2 logic.

## Repository Architecture

```text
trackflow/
├── AGENTS.md
├── CLAUDE.md
├── README.md
├── memory-bank/
├── .agents/
├── apps/
│   ├── marketing-site/
│   └── talent-pipeline-tracker/
├── uis/
│   ├── website/
│   └── backoffice/
├── packages/
│   ├── shared/
│   └── tailwind-config/
├── services/
├── agents/
├── skills/
├── data/
├── workflows/
├── scripts/
├── resources/
└── docs/
```

## Delivered Engagements

- Engagement 1 - Corporate Website & B2B Lead Capture: `apps/marketing-site/`
- Engagement 2 - Inventory & Carrier Scoring Engine: `packages/shared/`
- Engagement 3 - Talent Pipeline Tracker: `apps/talent-pipeline-tracker/`
- Engagement 4 - AI-Driven Engineering Infrastructure: `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/`, and npm workspace wiring

## Architectural Decisions

- `apps/` and `uis/` may depend on `packages/`; `packages/` must never depend on applications.
- `apps/` is preserved for delivered historical apps. Engagement 1 and Engagement 3 stay there unless a future brief documents a migration.
- `uis/` is the forward-looking UI workspace for public and internal Next.js + TypeScript interfaces.
- `services/` is reserved for future APIs and backend services. It is not a workspace member until the first service lands.
- npm workspaces are wired for `apps/*`, `packages/*`, and `uis/*`.
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
