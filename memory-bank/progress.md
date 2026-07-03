# Progress

## Completed

- Engagement 1 - Corporate Website & B2B Lead Capture (`docs/briefs/01-website.md`): delivered in `apps/marketing-site/`; code retired June 2026, surface now served by `uis/website/` (see `docs/archive/marketing-site-retirement.md`).
- Engagement 2 - Inventory & Carrier Scoring Engine (`docs/briefs/02-inventory-carriers.md`): delivered in `packages/shared/`.
- Engagement 3 - Talent Pipeline Tracker (`docs/briefs/03-talent-pipeline-tracker.md`): delivered in `apps/talent-pipeline-tracker/`; code retired June 2026, now lives at `uis/backoffice/app/talent/` (see `docs/archive/talent-pipeline-tracker-retirement.md`).
- Engagement 4 - AI-Driven Engineering Infrastructure (`docs/briefs/04-ai-driven-engineering.md`): delivered in `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, and `services/`.
- Engagement 5 - Backend Inventory Management (`docs/briefs/05-backend-inventory-management.md`): delivered in `services/central-api/` with FastAPI, SQLModel, Alembic, PostgreSQL inventory movements, Identity token verification, idempotent seed data, and disposable-database tests.

## Active

_None — Engagement 6 is the next planned engagement._

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

- Engagement 6 - Data pipelines and telemetry.
- Engagement 7 - RAG knowledge base and semantic search.
- Engagement 8 - AI agents.
- Engagement 9 - Workflow automation with n8n.
- Engagement 10 - Real-time dashboards and alerts.
- Production execution of the prepared Coolify/Supabase deployment, restore
  drills, and Supplier Directory retirement after its observation window.

## Open Decisions And Known Risks

- Lead-form persistence remains deferred and is not part of Engagement 5.
- No CI workflow exists yet; add one in a follow-up.
- Junecoast tokens are duplicated across `uis/website/` and `uis/backoffice/`; promoting them into a shared package is a follow-up. (The third copy disappeared with the June 2026 retirement of `apps/talent-pipeline-tracker/`.)
