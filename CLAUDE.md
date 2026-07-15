# Claude-Specific Orientation

Claude-specific orientation for AI coding agents working in this repo. For the cross-agent operating rules every agent must follow, read `AGENTS.md` first.

Claude sessions should read, in order:

1. `memory-bank/projectbrief.md`
2. `memory-bank/techContext.md`
3. `memory-bank/progress.md`
4. `AGENTS.md`
5. `README.md`
6. `CLAUDE.md`

Then read the active engagement brief and the README for every folder being modified.

## Repo Navigation

| If you're looking for... | Go here |
|---|---|
| Cross-agent operating rules | `AGENTS.md` |
| Persistent project context | `memory-bank/` |
| What this project is | `README.md` |
| Current engagement brief when assigned | `docs/briefs/NN-title.md` |
| All briefs | `docs/briefs/` |
| Cross-cutting standards and guidance | `docs/` |
| Engineering quality and telemetry standards (testing, error handling, observability, telemetry, production readiness) | `docs/standards/` |
| Operational runbooks (deployment, etc.) | `docs/runbooks/` |
| Intended CI workflow architecture | `.github/workflows/README.md` |
| Repo-specific quality remediation/improvement plans | `docs/planning/` |
| Archived planning artifacts | `docs/archive/` |
| Coding-agent scoped rules and skills | `.agents/` |
| Forward-looking UI workspace | `uis/` |
| Future backend services and APIs | `services/` |
| Engagement 1 surface (original app retired June 2026) | `uis/website/` + `docs/archive/marketing-site-retirement.md` |
| Engagement 3 tracker (standalone app retired June 2026) | `uis/backoffice/app/talent/` + `docs/archive/talent-pipeline-tracker-retirement.md` |
| Shared TypeScript code | `packages/shared/` |
| Shared incident contracts and CSV validation | `packages/trackflow_incidents/` |
| Non-code shared resources | `resources/` |
| Product AI agents | `agents/` |
| Data pipelines | `data/` |
| Workflow automations | `workflows/` |
| Product agent capabilities | `skills/` |
| Repo-wide scripts and utilities | `scripts/` |
| Container and deployment definitions | `docker/`, `compose.yaml`, `compose.coolify.yaml` |

## Where New Engagement Code Goes

- **Engagement 1** - delivered in `apps/marketing-site/`  
  Built; code retired June 2026. Surface lives at `uis/website/` — see `docs/archive/marketing-site-retirement.md`.

- **Engagement 2** - `packages/shared/`  
  Built.

- **Engagement 3** - delivered in `apps/talent-pipeline-tracker/`  
  Built; code retired June 2026. Now at `uis/backoffice/app/talent/` — see `docs/archive/talent-pipeline-tracker-retirement.md`.

- **Engagement 4** - `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/`  
  Built.

- **Engagement 5** - `services/central-api/`
  Built. Inventory, the Centralized Incident Manager, and the boundary-waived
  Supplier Directory use separate domains in this service. See
  `docs/briefs/05-backend-inventory-management.md`,
  `docs/planning/centralized-incident-manager.md`, and
  `docs/planning/supplier-directory-postgres-migration.md`.

- **Engagement 6** - Data Pipelines & Telemetry
  In progress. A `telemetry` domain in `services/central-api/` (table
  `telemetry_events`, exact metrics from `StockEntry`/`StockExit`, best-effort
  post-response diagnostics, enforced retention), Identity auth audit logs in
  `services/identity/`, and a Back Office Telemetry route in `uis/backoffice/`.
  A follow-on **live operations feed** makes the portfolio-production deployment
  feel live: `services/central-api/central_api/domains/operations/` (the
  `operations_feed_control` kill switch), `services/central-api/scripts/operations_feed.py`
  (single-writer worker) and `scripts/db_size_guard.py` (Supabase-Free bounding),
  plus `uis/backoffice/lib/hooks/useAutoRefresh.ts`, `components/OperationsOverview.tsx`
  (the new live landing), and the Engagement-2 scoring demo relocated to
  `/backoffice/carrier-scoring`. See `docs/briefs/06-data-pipelines-telemetry.md`,
  `docs/runbooks/operations-feed.md`, and the living signal reference
  `docs/runbooks/telemetry-inventory.md`.
  Production hardening lives in `data/pipelines/business_performance/worker.py`,
  `services/central-api/scripts/{maintenance_worker,production_migrate}.py`, the root Compose
  files, and `.github/workflows/deploy-production.yml`. The dedicated-Prefect remediation now has
  private Prefect Server/PostgreSQL wiring and a SQLite-fallback guard verified locally; later
  execution, recovery, operator, and external acceptance phases remain.

- **Engagement 7+** - TBD per engagement.
  Confirm with Cory before placing new code.

## Coding-Agent Infrastructure Vs. Product Agents

For the `.agents/` vs `agents/` vs `skills/` distinction, see the canonical table in `AGENTS.md`.

## Claude Notes

- Prefer `rg` and `rg --files` for searches.
- Before public-facing UI work, apply `.agents/rules/public-ui-visibility.md` and follow its linked `docs/standards/visibility.md`.
- Before auth, session, token, cookie, authorization, or AI-agent user-context work, apply `.agents/rules/authentication-security.md` and follow its linked `docs/standards/authentication-security-standard.md`.
- Before database or persistent-storage design, queries, schemas, repositories, migrations, seeds, recovery, or operations, apply `.agents/rules/database-engineering.md` and follow its linked `docs/standards/database-engineering-standard.md`.
- Before telemetry design or instrumentation (events, metrics, traces, correlation IDs, audit/security telemetry, analytics, retention, or AI telemetry), apply `.agents/rules/telemetry.md` and follow its linked `docs/standards/telemetry-standard.md`.
- Before adding or changing behavior in code, APIs, validation, failure paths, logging, or CI/deploy config, apply `.agents/rules/testing-error-handling-ci.md` and follow the relevant linked engineering-quality standard in `docs/standards/` (testing, error-handling, observability, production-readiness).
- Empty folders with READMEs are intentional scaffolding for future engagements.
