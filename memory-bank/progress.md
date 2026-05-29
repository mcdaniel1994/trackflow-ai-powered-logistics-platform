# Progress

## Completed

- Engagement 1 - Corporate Website & B2B Lead Capture (`docs/briefs/01-website.md`): delivered in `apps/marketing-site/`.
- Engagement 2 - Inventory & Carrier Scoring Engine (`docs/briefs/02-inventory-carriers.md`): delivered in `packages/shared/`.
- Engagement 3 - Talent Pipeline Tracker (`docs/briefs/03-talent-pipeline-tracker.md`): delivered in `apps/talent-pipeline-tracker/`.
- Engagement 4 - AI-Driven Engineering Infrastructure (`docs/briefs/04-ai-driven-engineering.md`): delivered in `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, and `services/`.

## Active

_None — Engagement 5 (Central API) is the next planned engagement._

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
- Framework dependencies in `apps/talent-pipeline-tracker/package.json` are pinned to `latest`; a version-pinning sweep is a follow-up.
- No CI workflow exists yet; add one in a follow-up.
- Junecoast tokens are duplicated across `uis/website/`, `uis/backoffice/`, and `apps/talent-pipeline-tracker/`; promoting them into a shared package is a follow-up.
- `apps/marketing-site/assets/css/styles.css` still contains an overridden Slate and Gold token block; it is left untouched because the delivered marketing site is protected.
