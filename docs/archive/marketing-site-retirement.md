# Retirement Note: Marketing Site (`apps/marketing-site/`)

**Engagement:** 1 — Corporate Website & B2B Lead Capture (`docs/briefs/01-website.md`)
**Original path:** `apps/marketing-site/`
**Replaced by:** `uis/website/` (Next.js + TypeScript component refactor of the same surface: `/`, `/application`, `/privacy`)
**Retired:** June 2026

## Why it was deleted

Engagement 1 delivered the corporate site as a static HTML/Tailwind/vanilla-JS app. Engagement 4 refactored that surface into the forward-looking Next.js workspace at `uis/website/`, and the live Vercel deployment builds from `uis/website/`. With active UI work consolidated into `uis/`, the standalone static app no longer had a runtime consumer. Before deletion it was verified that `uis/website/` lints, type-checks, builds, and covers the delivered surface page-for-page (`index.html` → `/`, `application.html` → `/application`, `privacy.html` → `/privacy`).

The engagement itself remains delivered; this note preserves the history. The original code is recoverable from git history prior to the retirement commit.

## `packages/tailwind-config/` retired with it

`packages/tailwind-config/` existed solely to compile the marketing site's Tailwind CSS (`build:marketing-site` and `watch` both wrote to `apps/marketing-site/assets/css/styles.css`; its default `build` was an intentional no-op). With no remaining consumer — the `uis/` apps each carry their own Tailwind config — the package was deleted in the same retirement.
