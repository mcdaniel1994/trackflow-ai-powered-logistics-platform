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
| 06 | [Data Pipelines & Telemetry](06-data-pipelines-telemetry.md) | Andrés Kim, CTO | 🚧 Startup hotfix locally verified; production acceptance pending | `data/`, `services/central-api/`, `services/identity/`, `uis/backoffice/`, `.github/workflows/` |

## Conventions

- Filenames: `NN-short-slug.md`
- Each brief opens with a one-line stakeholder identification and a Status section.
- Briefs are stakeholder voice — do not rewrite for uniformity once delivered.
