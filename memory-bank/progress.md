# Progress

## Completed

- Engagement 1 - Corporate Website & B2B Lead Capture (`docs/briefs/01-website.md`): delivered in `apps/marketing-site/`; code retired June 2026, surface now served by `uis/website/` (see `docs/archive/marketing-site-retirement.md`).
- Engagement 2 - Inventory & Carrier Scoring Engine (`docs/briefs/02-inventory-carriers.md`): delivered in `packages/shared/`.
- Engagement 3 - Talent Pipeline Tracker (`docs/briefs/03-talent-pipeline-tracker.md`): delivered in `apps/talent-pipeline-tracker/`; code retired June 2026, now lives at `uis/backoffice/app/talent/` (see `docs/archive/talent-pipeline-tracker-retirement.md`).
- Engagement 4 - AI-Driven Engineering Infrastructure (`docs/briefs/04-ai-driven-engineering.md`): delivered in `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, and `services/`.

## Active

_None — Engagement 5 (Central API) is the next planned engagement._

## Subprojects

- Incident Report Processor (spec: `docs/planning/incident-report-processor.md`) — built; explicitly **not** Engagement 5. Lives in `services/incident-processor/` (FastAPI + analysis core), `scripts/analyze.py` (CLI wrapper), and the backoffice `/incidents` route (`uis/backoffice/app/incidents/`). The local dataset `scripts/incidents-trackflow.csv` is git-ignored and protected by `.agents/rules/sensitive-local-datasets.md`.
- Supplier Directory (spec: `docs/planning/supplier-directory.md`) — built; explicitly **not** Engagement 5. Lives in `services/supplier-directory/` (FastAPI + TinyDB + idempotent seed command) and the backoffice supplier routes (`/suppliers`, `/suppliers/new`, `/suppliers/[id]`). The generated TinyDB file `services/supplier-directory/data/suppliers.json` is git-ignored, and default list/detail responses expose only `has_contact_email`; raw contact email is revealed only from the supplier detail page.
- Auth 1 Backend Authentication and API Route Protection (spec: `docs/planning/auth/plans/auth-1-implementation-plan.md`) — backend implementation in progress; explicitly **not** Engagement 5. Lives in `services/identity/` (FastAPI + TinyDB users/refresh sessions) and `packages/trackflow_auth/` (verify-only token/CSRF helpers), and protects the `supplier-directory` and `incident-processor` business endpoints. Auth 2 frontend login and Auth 3 password reset remain deferred.

## Migration Decisions

- June 2026 — Talent Pipeline Tracker migrated from `apps/talent-pipeline-tracker/` into `uis/backoffice/app/talent/` (routes `/talent`, `/talent/new`, `/talent/[id]`; env var renamed to `NEXT_PUBLIC_TALENT_API_URL`). The standalone app was deleted after the migration was verified (lint, type-check, build, route smoke tests).
- June 2026 — `apps/` retired entirely: `apps/marketing-site/` deleted after verifying `uis/website/` covers its surface page-for-page, and `packages/tailwind-config/` deleted with it (its only purpose was compiling the marketing site CSS). Retirement notes live in `docs/archive/`.

## Planned Next

- Engagement 5 - Central API.
- Engagement 6 - Data pipelines and telemetry.
- Engagement 7 - RAG knowledge base and semantic search.
- Engagement 8 - AI agents.
- Engagement 9 - Workflow automation with n8n.
- Engagement 10 - Real-time dashboards and alerts.

## Open Decisions And Known Risks

- Lead-form persistence is deferred to Engagement 5 and should be wired to the Central API when that service exists.
- Backoffice authentication is deferred to Engagement 5; Engagement 4 intentionally ships the internal shell without login.
- No CI workflow exists yet; add one in a follow-up.
- Junecoast tokens are duplicated across `uis/website/` and `uis/backoffice/`; promoting them into a shared package is a follow-up. (The third copy disappeared with the June 2026 retirement of `apps/talent-pipeline-tracker/`.)
