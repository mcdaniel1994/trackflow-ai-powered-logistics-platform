# Agent Orientation

Orientation file for AI coding agents working in this repo. Read this before making changes.

---

## Read These First, in This Order

1. **`README.md`**  
   What the project is, what’s built, what’s planned, repo architecture, and tech stack.

2. **`docs/briefs/`**  
   Every engagement has a stakeholder brief here. The brief is the source of truth for what that engagement needs to deliver.  
   Read the brief for whatever engagement is being worked on before writing any code.

3. **The README in the folder you're working in**  
   Every meaningful folder has one explaining its purpose.

> If a question is answered by one of those files, don’t ask — read it.

---

## Repo Navigation

| If you're looking for... | Go here |
|---|---|
| What this project is | `README.md` |
| Active brief | `docs/briefs/NN-slug.md` |
| Past briefs | `docs/briefs/` |
| Archived course and planning artifacts from bootcamp setup | `docs/archive/` |
| Cross-cutting docs | `docs/` |
| Engagement 1 deliverable | `apps/marketing-site/` |
| Shared TypeScript code (types, utilities) | `packages/shared/` |
| Tailwind build setup | `packages/tailwind-config/` |
| Non-code shared resources (schemas, templates, config assets) | `resources/` |
| AI agents | `agents/` |
| Data pipelines | `data/` |
| Workflow automations | `workflows/` |
| Reusable agent capabilities | `skills/` |
| Repo-wide scripts and utilities | `scripts/` |

---

## Where New Engagement Code Goes

- **Engagement 1** — `apps/marketing-site/`  
  Built.

- **Engagement 2+** — TBD per engagement.  
  Confirm with Cory before placing new code.

---

## Public-Facing UI & Frontend Work

Before doing any work on public-facing pages, marketing content, or frontend HTML — **read `docs/standards/visibility.md` first.**

This file is the authority on how TrackFlow's public pages get found by search engines, AI engines, and human visitors. It governs semantic HTML, WCAG 2.1 AA accessibility, SEO metadata, GEO formatting, Schema.org structured data, Core Web Vitals targets, and bot access rules.

All generated public pages must comply with sections 1 through 6 of that file. Do not generate or modify a public-facing page without reading it first.

This applies to:
- `apps/marketing-site/` (current)
- Any future public portal pages, blog, knowledge base, or documentation

---

## Repo Rules

- `apps/` depends on `packages/`. Never the reverse.
- Empty folders with READMEs are intentional scaffolding for future engagements. Do **not** delete them.