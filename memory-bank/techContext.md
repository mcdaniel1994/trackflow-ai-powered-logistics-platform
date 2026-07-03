# Technical Context

## Current Stack

- `packages/shared/` - delivered Engagement 2 strict TypeScript domain types and pure utilities for inventory, carrier scoring, shipping costs, reporting, search, and validation.
- `packages/trackflow_auth/` - Python verify-only authentication helper package for RS256 access-token validation and CSRF checks in backend services.
- `uis/website/` - public Next.js + TypeScript website (Engagement 4); sole home of the Engagement 1 marketing surface since the static `apps/marketing-site/` was retired in June 2026.
- `uis/backoffice/` - internal Next.js + TypeScript shell (Engagement 4) that consumes Engagement 2 logic; hosts the Talent Pipeline Tracker at `/talent` (Engagement 3, migrated June 2026) and the Centralized Incident Manager at `/incidents`.
- `services/identity/` - Python/FastAPI + TinyDB identity service for Auth 1 backend authentication, refresh sessions, and user management.
- `services/central-api/` - Python/FastAPI modular monolith for inventory,
  incidents, and suppliers, with SQLModel, Alembic, and PostgreSQL; it verifies
  Identity tokens through `trackflow_auth` and never opens Identity's TinyDB.
- `compose.yaml` and `compose.coolify.yaml` define separate local and production
  paths for Identity, Central API, and Back Office.
- The production stack is verified on Coolify at
  `https://backoffice.forgehub.cloud`. Back Office is the only public service;
  Identity and Central API remain private on the Coolify network. Supabase uses
  separate runtime and migration roles through the IPv4 Supavisor Session
  pooler, and the current schema is at Alembic revision `20260702_0003`.
- `.github/workflows/container-images.yml` builds Linux AMD64 production images
  on GitHub-hosted runners and publishes commit-pinned tags to GHCR; the
  production Compose stack pulls rather than builds them on the VPS.
- `packages/trackflow_incidents/` - shared Python incident enums, privacy-safe
  legacy CSV validation, and normalization used by Central API.

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
│   ├── shared/
│   └── trackflow_auth/
├── services/
│   ├── identity/
│   ├── central-api/
│   └── supplier-directory/  # temporary rollback copy pending observation
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
- Engagement 5 - Backend Inventory Management: `services/central-api/` FastAPI modular monolith with SQLModel, Alembic, PostgreSQL, Identity token verification, and transactional inventory movements

## Architectural Decisions

- `uis/` may depend on `packages/`; `packages/` must never depend on applications.
- `apps/` was retired in June 2026: active UI work lives in `uis/`, and retired delivered code is preserved via `docs/archive/` retirement notes plus git history, not on-disk copies.
- `uis/` is the sole UI workspace for public and internal Next.js + TypeScript interfaces.
- `services/` hosts independently managed backend services. Python/FastAPI services are intentionally not npm workspace members. Engagement 5 lives in `services/central-api/`.
- Auth 1 backend authentication lives in `services/identity/` with reusable verification helpers in `packages/trackflow_auth/`; Central API consumes those helpers while Identity remains the sole TinyDB owner.
- Identity validates that its RS256 private/public PEM values are complete,
  parseable, RSA, and matching before opening storage or becoming healthy.
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
