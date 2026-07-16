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
  paths for Identity, Central API, Back Office, a private digest-pinned Prefect 3.7.8 Server,
  dedicated PostgreSQL 16 orchestration state, an image-baked idempotent database bootstrap,
  reporting/maintenance workers, and an isolated read-only Prefect database backup service.
- The production stack is verified on Coolify at
  `https://backoffice.forgehub.cloud`. Back Office is the only public service;
  Identity and Central API remain private on the Coolify network. Supabase uses
  separate runtime and migration roles through the IPv4 Supavisor Session
  pooler, and the current schema is at Alembic revision `20260716_0010`.
- `.github/workflows/release-checks.yml` runs production-target lint, typing,
  tests/coverage, and builds before `.github/workflows/container-images.yml`
  publishes Linux AMD64 commit-pinned images to GHCR.
- `.github/workflows/deploy-production.yml` is the reusable and manually
  dispatchable, GitHub-Environment-gated path that preflights all three
  immutable images, runs approval-gated migrations for releases, verifies the static Prefect
  contract, updates only Coolify's `TRACKFLOW_IMAGE_TAG`, polls readiness, and automatically
  restores the prior app image on failure without downgrading databases. Image rollback does not
  restore an older Compose topology, so Compose failures require a reviewed forward fix or an
  explicitly approved prior-revision deployment. Coolify
  `4.1.2` and the GitHub Production environment are configured for this path;
  its first live approved run exposed the July 15 Prefect init-mount defect; the repository hotfix
  awaits approved redeployment and the rollback drill remains an owner step.
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
- Engagement 6 business reporting uses TrackFlow PostgreSQL `reporting.pipeline_runs` as its sole
  dispatch authority. Prefect has no work pool and owns only orchestration history/recovery state in
  a separate database. The worker renews leases independently, records token-CAS correlation/stage
  progress, fails closed on Prefect health, and is bounded by a hard watchdog. Optional R2 recovery
  results and backups are non-authoritative and separately credentialed.
- Reporting readiness and the API share one six-state derivation (`idle`, `processing`, `queued`,
  `retrying`, `stuck`, `unavailable`). One-shot Compose guards prove Prefect tables live in
  PostgreSQL and the digest-pinned server is compatible with the locked client before worker startup.
- Prefect PostgreSQL init files are copied into a digest-pinned custom image rather than mounted
  from relative repository paths. A one-shot idempotent bootstrap runs after database liveness on
  every deployment, repairs missing prerequisites on existing volumes, and gates Prefect Server and
  backups. Central API container health uses `/health/live`; dependency-aware `/health/ready`
  remains a release-level check after the full service graph starts.

## Folder Boundaries

- `memory-bank/`, `AGENTS.md`, and `.agents/` are coding-agent infrastructure for maintaining this repository.
- `agents/` and `skills/` are product architecture for future TrackFlow AI agents and their reusable business capabilities.
- `data/` is for future raw data, processed data, pipelines, and evaluation datasets.
- `workflows/` is for future n8n automation workflows.
- `resources/` is for non-code shared resources such as schemas, templates, and configuration assets.
