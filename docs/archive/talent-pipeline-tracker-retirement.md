# Retirement Note: Talent Pipeline Tracker (`apps/talent-pipeline-tracker/`)

**Engagement:** 3 — Talent Pipeline Tracker (`docs/briefs/03-talent-pipeline-tracker.md`)
**Original path:** `apps/talent-pipeline-tracker/`
**Replaced by:** `uis/backoffice/app/talent/` — the tracker now lives inside the backoffice shell:
- Routes: `/talent` (candidate list), `/talent/new` (registration), `/talent/[id]` (detail, edit, notes)
- Components: `uis/backoffice/components/talent/` (domain) and `uis/backoffice/components/talent/ui/` (form/button kit)
- API client and types: `uis/backoffice/lib/talent/` (`api.ts`, `types.ts`, `labels.ts`)
- Backend base URL env var: `NEXT_PUBLIC_TALENT_API_URL` (renamed from `NEXT_PUBLIC_API_URL` to avoid colliding with the incident processor client's fallback; default remains the 4Geeks playground API)

**Retired:** June 2026

## Why it was deleted

Engagement 3 delivered the tracker as a standalone Next.js app. As internal tools consolidated into the `uis/backoffice/` shell (inventory + carriers, incidents), running a separate app for one internal recruiting view stopped earning its overhead — separate dependency set (pinned to `latest`), no lint/type-check scripts, and a duplicate copy of the Junecoast palette. The full feature set was migrated into the backoffice under the pinned, linted toolchain and verified (lint, type-check, build, and route smoke tests) before this deletion.

The engagement itself remains delivered; this note preserves the history. The original code is recoverable from git history prior to the retirement commit.
