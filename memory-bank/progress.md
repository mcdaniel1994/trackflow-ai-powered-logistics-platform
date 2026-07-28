# Progress

## Completed

- Engagement 1 - Corporate Website & B2B Lead Capture (`docs/briefs/01-website.md`): delivered in `apps/marketing-site/`; code retired June 2026, surface now served by `uis/website/` (see `docs/archive/marketing-site-retirement.md`).
- Engagement 2 - Inventory & Carrier Scoring Engine (`docs/briefs/02-inventory-carriers.md`): delivered in `packages/shared/`.
- Engagement 3 - Talent Pipeline Tracker (`docs/briefs/03-talent-pipeline-tracker.md`): delivered in `apps/talent-pipeline-tracker/`; code retired June 2026, now lives at `uis/backoffice/app/talent/` (see `docs/archive/talent-pipeline-tracker-retirement.md`).
- Engagement 4 - AI-Driven Engineering Infrastructure (`docs/briefs/04-ai-driven-engineering.md`): delivered in `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, and `services/`.
- Engagement 5 - Backend Inventory Management (`docs/briefs/05-backend-inventory-management.md`): delivered in `services/central-api/` with FastAPI, SQLModel, Alembic, PostgreSQL inventory movements, Identity token verification, idempotent seed data, and disposable-database tests.
- Production deployment checkpoint (verified July 2, 2026 America/Chicago):
  Coolify serves the authenticated Back Office over HTTPS while Identity and
  Central API remain private; Supabase is migrated through `20260702_0003`,
  inventory and suppliers are seeded, and production incidents remain empty.

## Active

- Engagement 6 - Data Pipelines & Telemetry (`docs/briefs/06-data-pipelines-telemetry.md`):
  in progress. Reporting-reliability Phase 6.1 is deployed as immutable image `13bba2e` through
  Alembic `20260728_0011` and closed by explicit owner exception after the remaining controlled
  exercises were omitted on 2026-07-28. Phase 6.2 additive revision `20260728_0012` is deployed
  and owner-accepted after its corrected 1,266-row publication, exact 12-dimension reconciliation,
  and 35.573-second durable attempt. Phase 6.3 is deployed through additive revision
  `20260728_0013`, with atomic reconciled weekly activation, hourly current-week reads,
  transient-only inner retries, computation-disable/verified-stale rollback modes, and operator
  status/UI. Its first controlled run published a verified six-row snapshot, and rollback drill one
  passed with safe 503, explicit stale serving, unrelated-route isolation, unchanged snapshot
  lineage, and no unexpected queue work. Rollback drill two and the required seven-day observation
  remain pending.
  Independent Phases 6.5.a–b are
  owner-accepted and complete as an offline
  evaluation: the relocated,
  deterministic 120-month generated dataset feeds an offline strict-recursive Random Forest
  baseline with versioned metrics/model/chart/report artifacts. Five chronological folds produce
  validation RMSE 50,273 ± 13,165 EUR and diagnose overfitting caused by bounded absolute-level
  extrapolation; the artifact is not approved for operational use.
  Phase 1 added a Central API `telemetry` domain with a `telemetry_events` table,
  exact warehouse metrics read from `StockEntry`/`StockExit`, best-effort post-response
  rejected-dispatch and `api.access.denied` diagnostics, Identity auth audit logs (logs only),
  enforced retention, bounded aggregates-only reporting endpoints, and a read-only Back Office
  Telemetry route (Fulfilment/Security). A follow-on **live operations feed** slice makes the
  portfolio-production Back Office feel live: a single-writer worker
  (`scripts/operations_feed.py`, pg advisory lock + `operations_feed_control` kill switch) writes
  real synthetic-but-canonical inventory movements ~every 5s so exact metrics stay live and
  reconcilable; dashboards auto-refresh ~5s without flicker (`lib/hooks/useAutoRefresh.ts`) and a
  new live **Operations Overview** replaces the static "Inventory + Carriers" landing (the
  Engagement-2 scoring demo moved to `/backoffice/carrier-scoring`). Production telemetry is now
  enabled with 7-day retention, a daily prune, and a `scripts/db_size_guard.py` size guard
  (400 MB soft / 450 MB hard, ledger-safe reset) that keeps Supabase Free bounded. Runbook:
  `docs/runbooks/operations-feed.md`; signal reference: `docs/runbooks/telemetry-inventory.md`.
  The dedicated-Prefect remediation has completed repository Phases 0-4 locally: a private digest-pinned Prefect
  3.7.8 Server stores orchestration state in its own PostgreSQL 16 volume, both reporting clients
  target it, and a release guard proves Prefect tables live in PostgreSQL rather than fallback
  SQLite. The worker now renews claims independently, records token-guarded Prefect run IDs and
  stages, fails closed on orchestrator health, reconciles orphaned runs, and has a hard execution
  watchdog with truthful readiness signals. `reporting.pipeline_runs` remains the sole dispatch
  authority. Optional transformation recovery results use a distinct R2 prefix, the maintenance
  worker prunes old terminal runs through the API only, and a pinned read-only backup service creates
  daily custom-format dumps with distinct `PREFECT_BACKUP_R2_*` credentials. The absent-R2 path and
  an isolated scratch restore are locally verified. The reporting API and Back Office now share six
  server-derived queue states, and the reporting worker's own fail-closed startup guard blocks it on
  SQLite fallback or incompatible server/client versions. The July 15 first production startup exposed
  Coolify translating PostgreSQL init-file bind mounts into directories; the hotfix now bakes those
  files into the pinned database image, repairs existing volumes through an idempotent one-shot
  bootstrap, and keeps Central API container liveness independent of reporting readiness. The hotfix
  redeployment then ended as Coolify exit 255 — the SSH command boundary, not a guard rejection
  (a real guard failure exits 1 in ~13s). `up -d` stays attached until every
  `service_completed_successfully` dependency exits, so gating the worker on the one-shot guards put
  them on the deploy critical path. The guards now report without gating startup, enforcement moved
  into the worker, guards emit fixed tokens, and `scripts/release/measure_compose_startup.sh` makes
  the attach time measurable (18s chain against ~3GB of per-deployment pulls). Approved
  redeployment is complete. The Phase 6.3 control-plane outage/restore drill passed; external
  production soak, Prefect restore, 48-hour headroom, scheduled-run, computation-disable, and
  image-rollback acceptance measurements remain.
  The earlier production-hardening slice replaces manual reporting recovery and Coolify cron jobs with
  always-on reporting and maintenance workers, fixes Prefect failure propagation, exposes worker
  health, adds fail-closed migration/grant verification, introduces `/health/live` and
  `/health/ready`, and automatically restores the previous immutable image after deploy or
  readiness failure. The GitHub Production secret is configured; credential rotation remains an
  owner action. Rollback drill one is complete; the separate computation-disable drill remains an
  owner acceptance action.
  Browser analytics, a durable event queue, correlation IDs, metrics/tracing backends, real
  carriers tables, and AI telemetry remain explicitly deferred.

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

All remaining work is planned from `docs/planning/remaining_planning/`. Its
`README.md` is the index, sequence, and precedence rule between owner-approved
specifications and bootcamp planning inputs — read it before planning or
implementing any of the items below.

- Engagement 6.1-6.4 - reporting reliability remediation. Owner-approved
  specification: `docs/planning/remaining_planning/spec.md`. Phase 6.1 is closed by documented
  owner exception. Phase 6.2 is production-accepted. Phase 6.3 is deployed through
  `20260728_0013`; controlled rollout steps 1-6 and rollback drill one passed. Rollback drill two
  and the seven-day observation remain; Phase 6.4 remains blocked until explicit Phase 6.3
  acceptance.
- Engagement 6.5 - sales forecasting. Owner-approved specification:
  `docs/planning/remaining_planning/spec-6.5-sales-forecasting.md`. Independent of
  6.1-6.4 and runs in parallel with it, not after. Phases 6.5.a–b are complete and owner-accepted
  as an offline evaluation; the overfitting model remains prohibited from operational use.
- Engagement 7 - RAG knowledge base and semantic search. Planning inputs only; no
  specification yet.
- Engagement 8 - AI agents (LangGraph, tools, MCP server with OAuth, guardrails,
  memory). Planning inputs only; no specification yet.
- Engagement 9 - Agentic workflows for the RFP desk. Planning inputs only; no
  specification yet. This is LangGraph work, not n8n; the earlier "workflow
  automation with n8n" framing does not match the assignment documents.
- Engagement 10 - Real-time dashboards and alerts. Blocked: the requirements
  document `10_realtime/realtime.md` is empty.
- Cross-cutting backlog (`important_considerations/others.md`): website
  contact-form lead persistence, a job-applicant form plus migration off the
  third-party talent API, and a Back Office information-architecture
  restructure. Fold each into the engagement that forces it rather than creating
  a new engagement number.
- Production restore drills and Supplier Directory retirement after its
  observation window.

## Open Decisions And Known Risks

- Lead-form persistence remains deferred and is not part of Engagement 5.
- Production-target release checks now gate GHCR image publishing, and eligible
  `main` builds proceed to an approval-gated, SHA-pinned Coolify deployment.
  The Coolify `4.1.2` and GitHub Production environment prerequisites are
  configured. Broad PR CI, browser E2E, and dependency/secret scanning remain
  follow-ups; the first live automated deployment exposed the documented Prefect startup defect,
  while the July 28 immutable deployment verified its hotfix and Phase 6.1. The owner omitted the
  remaining Phase 6.1 exercises. Phase 6.3 rollback drill one has now run successfully; drill two
  remains pending separate owner approval.
- Supabase Free and the Identity volume have no scheduled backups under the
  accepted disposable-data waiver; meaningful production data requires
  revisiting backup and restore requirements first.
- Junecoast tokens are duplicated across `uis/website/` and `uis/backoffice/`; promoting them into a shared package is a follow-up. (The third copy disappeared with the June 2026 retirement of `apps/talent-pipeline-tracker/`.)
