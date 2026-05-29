# Engagement 04 — AI-Driven Engineering Infrastructure: Implementation Plan

**Context.** Engagements 1–3 are delivered. Per [docs/briefs/04-ai-driven-engineering.md](docs/briefs/04-ai-driven-engineering.md), this engagement builds the engineering infrastructure that lets the monorepo grow without losing context: persistent project memory for coding agents, a cross-agent operating guide, scoped agent rules + a reusable skill, a new `uis/` workspace housing a Next.js public website and an internal backoffice, a reserved `services/` boundary, and a **minimal npm workspace so `uis/backoffice` can cleanly consume `packages/shared` as `@repo/shared-types`**. Engagement 3's app has already been renamed from `apps/uis/` to [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/); a few stale `apps/uis` references inside [apps/talent-pipeline-tracker/spec.md](apps/talent-pipeline-tracker/spec.md) must be corrected. Delivered Engagements 1, 2, 3 stay intact.

All decisions are locked. There are no remaining open questions about scope or palette.

---

## 1. Required Engagement 04 Work

### 1.0 Locked decisions

| Decision | Value |
|---|---|
| Workspace tooling | **npm workspaces.** Required Engagement 04 work, not optional. Root `package.json` with `"private": true` and `"workspaces": ["apps/*", "packages/*", "uis/*"]`; root `.nvmrc`. |
| `uis/backoffice` ↔ `packages/shared` | **`import … from "@repo/shared-types"`** only. No relative `../../packages/shared/src/...` paths. |
| Active visual palette | **Junecoast** (the `--jc-*` token set already live in production). Used by `uis/website`, `uis/backoffice`, and (already) [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/). The stale `--tf-slate-*` / `--tf-gold-*` block in [apps/marketing-site/assets/css/styles.css](apps/marketing-site/assets/css/styles.css) is overridden by a later `--jc-*` block (confirmed in [apps/talent-pipeline-tracker/spec.md:243](apps/talent-pipeline-tracker/spec.md#L243)) and is **not** carried into the new React site. |
| Lead form submission target | **No real backend in Engagement 04.** Validate, render a local success state. Real persistence/API submission is deferred to Engagement 5; documented in `memory-bank/progress.md`. |
| Backoffice authentication | **No login screen in Engagement 04.** Build the internal shell without auth. Auth deferred to Engagement 5; documented in `memory-bank/progress.md`. |
| Language toggle in `uis/website` | **Preserve the existing client-side EN/ES language toggle.** Specifically: (a) use typed `Locale = "en" \| "es"`; (b) migrate the current `window.TRANSLATIONS` strings into typed React/TypeScript content modules; (c) persist the toggle state in `localStorage`; (d) update `document.documentElement.lang` on switch; (e) do **not** add separate Spanish routes or `hreflang` in Engagement 04 — those remain deferred per [docs/standards/visibility.md](docs/standards/visibility.md). |
| [apps/talent-pipeline-tracker/spec.md](apps/talent-pipeline-tracker/spec.md) edits | **Path corrections only** — update the three `apps/uis/` mentions (lines 41, 53, 252) to `apps/talent-pipeline-tracker/`. No other edits. |
| Delivered apps / package | [apps/marketing-site/](apps/marketing-site/), [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/), and `packages/shared/src/` are protected from behavior changes. Only the integration-only metadata edits to [packages/shared/package.json](packages/shared/package.json) listed in §1.1 are in scope. |
| Engagement 04 status | `⏳ Upcoming` before implementation → `🚧 In progress` during implementation → `✅ Delivered` **only after every §4 acceptance criterion passes**. |

### 1.1 Minimal npm workspace (required)

**Create root [package.json](package.json):**
```json
{
  "name": "trackflow",
  "private": true,
  "workspaces": ["apps/*", "packages/*", "uis/*"]
}
```
- No root scripts beyond what's necessary; root is an orchestration shell.
- [services/](services/) is intentionally not in `workspaces` yet — it holds no Node packages this engagement. It will be added when the first service lands.

**Create root [.nvmrc](.nvmrc):** contents are the single line `22` (matches the local environment — Node `v22.22.3`, npm `10.9.8`). Both new `uis/*` apps and the existing workspace members run under Node 22.

**Update [packages/shared/package.json](packages/shared/package.json) and add one barrel file — integration-only changes:**
- Current `"main": "src/utils/index.ts"` and `"types": "src/types/index.ts"` expose only one barrel from any single import path. To make `import { … } from "@repo/shared-types"` resolve **both** types and utilities:
  1. Add a single new file `packages/shared/src/index.ts` containing only `export * from "./types"; export * from "./utils";`
  2. Update `packages/shared/package.json` to set `"main": "src/index.ts"` and `"types": "src/index.ts"`
- **Explicitly untouched.** `packages/shared/src/types/**` and `packages/shared/src/utils/**` — every file under those directories — remain byte-for-byte unchanged. No business logic, no type declarations, no `README` files in those subdirectories are modified. The only acceptable edits inside [packages/shared/](packages/shared/) are the new `src/index.ts` barrel and the two-line `package.json` metadata update above.

**Consume the package from `uis/backoffice`:**
- Add `"@repo/shared-types": "*"` to `uis/backoffice/package.json` dependencies — npm workspaces resolves it to the in-repo path.
- In `uis/backoffice/next.config.ts`, add `transpilePackages: ["@repo/shared-types"]` so Next compiles the TS source on the fly. No build step in `packages/shared` is required.
- All consumption uses `import { … } from "@repo/shared-types"`. Zero relative path imports into `packages/shared/src/...`.

**Behavior under the new workspace:**
- [apps/marketing-site/](apps/marketing-site/) has no `package.json` (static HTML) — unaffected.
- [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/) participates by being listed in `workspaces` but requires no source changes.
- **Single authoritative lockfile.** After workspace adoption, the root `package-lock.json` is the only committed lockfile. Remove every nested workspace lockfile:
  - `apps/talent-pipeline-tracker/package-lock.json` — delete
  - `packages/tailwind-config/package-lock.json` — delete
  - `uis/website/` and `uis/backoffice/` — scaffolded so they do **not** keep their own `package-lock.json`; if `create-next-app` writes one, remove it before committing.

**Explicitly out of scope (not deferral of workspace setup itself — see §2):** root `tsconfig.base.json`, CI workflow, framework-version pinning sweep.

### 1.2 `memory-bank/` — persistent project context

Create [memory-bank/](memory-bank/) at the repo root with three TrackFlow-specific files (no generic boilerplate). Source material: [README.md](README.md), [CLAUDE.md](CLAUDE.md), every brief under [docs/briefs/](docs/briefs/).

- **`memory-bank/projectbrief.md`**
  - TrackFlow as a last-mile + warehouse logistics operator (LA + Zaragoza; US + Spain markets)
  - The six operational problems from the README (two warehouses / two systems, eight carriers with no unified data, manual returns, all-human support, no CRM, manual reporting)
  - Stakeholders introduced so far: Miguel Torres (Commercial), Ana Whitfield (Warehouse Ops), Andrés Kim (CTO), Javier (backend lead, per Engagement 3 brief)
  - Project objective: replace manual ops with reliable automation across a single cohesive platform spanning ten engagements

- **`memory-bank/techContext.md`** — reflects post-Engagement 04 state:
  - Current stack: HTML + Tailwind + vanilla JS ([apps/marketing-site/](apps/marketing-site/)); strict TypeScript ([packages/shared/](packages/shared/)); Next.js App Router + Tailwind ([apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/), [uis/website/](uis/website/), [uis/backoffice/](uis/backoffice/))
  - Repository architecture tree (the post-Engagement 04 tree from §5)
  - Delivered engagements with canonical paths: [apps/marketing-site/](apps/marketing-site/), [packages/shared/](packages/shared/), [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/)
  - Architectural decisions:
    - `apps/` and `uis/` depend on `packages/`; never the reverse
    - `apps/` is preserved for delivered historical apps
    - `uis/` is the forward-looking UI workspace (public + internal)
    - `services/` is reserved for future APIs
    - **npm workspaces wired for `apps/*`, `packages/*`, `uis/*`; `services/*` joins when the first service lands**
    - **`packages/shared` is consumed in this repo as `@repo/shared-types`** ([uis/backoffice/](uis/backoffice/) is the first consumer)
    - Public pages must comply with [docs/standards/visibility.md](docs/standards/visibility.md) sections 1–6
    - **Junecoast is the active visual palette across all current TrackFlow UIs**

- **`memory-bank/progress.md`** — reflects post-Engagement 04 state:
  - **Completed:** Engagements 1, 2, 3, 4 (each with brief link and delivered path; only flip Engagement 4 to Completed when §4 passes per §1.0)
  - **Active:** none upon Engagement 04 completion; in flight, list Engagement 4 here
  - **Planned next:** Engagements 5–10 (Central API, data pipelines, RAG, AI agents, n8n, dashboards)
  - **Open decisions / known risks (post-Engagement 04):**
    - Lead-form persistence: deferred to Engagement 5 (Central API)
    - Backoffice authentication: deferred to Engagement 5
    - Framework dependencies in [apps/talent-pipeline-tracker/package.json](apps/talent-pipeline-tracker/package.json) pinned to `"latest"`; pinning sweep is a follow-up
    - No CI workflow yet; follow-up
    - Junecoast tokens currently duplicated across three Tailwind configs ([uis/website/](uis/website/), [uis/backoffice/](uis/backoffice/), [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/)); promoting them into a shared package is a follow-up
    - [apps/marketing-site/assets/css/styles.css](apps/marketing-site/assets/css/styles.css) still contains the overridden Slate + Gold token block — left untouched per the protected-path rule
  - **Do not list:** "no root workspace tooling" or "`@repo/shared-types` is not consumed" — both are resolved by Engagement 04.

### 1.3 Root `AGENTS.md` — cross-agent operating guide

Create [AGENTS.md](AGENTS.md) as the **single source of truth for how any coding agent operates in this repository.**

Reframe [CLAUDE.md](CLAUDE.md) at the top: *"Claude-specific orientation. For the cross-agent operating rules every agent must follow, read [AGENTS.md](AGENTS.md) first."* No rule is duplicated between the two files; rules that apply to all agents live in `AGENTS.md`, and `CLAUDE.md` defers to it.

`AGENTS.md` must include:

- **Startup reading list** (every session, before any action): the three files in [memory-bank/](memory-bank/), then [AGENTS.md](AGENTS.md) itself, then [README.md](README.md). Claude additionally reads [CLAUDE.md](CLAUDE.md).
- **Pre-implementation reading**: the engagement brief at `docs/briefs/NN-<slug>.md`, plus the README of any folder being modified.
- **Mandatory pre-commit workflow** (≥4 ordered steps):
  1. Confirm the engagement brief and acceptance criteria for the change in flight
  2. Run `type-check`, `build`, and `lint` for every touched package or app
  3. Update the engagement-tracking docs that move together: [README.md](README.md) roadmap row + "What's Been Built", [docs/briefs/README.md](docs/briefs/README.md) index, the engagement brief's `## Status`, [CLAUDE.md](CLAUDE.md) "Where New Engagement Code Goes", `memory-bank/progress.md`, and the deliverable folder's README
  4. Verify no protected files were modified outside the engagement scope; write a commit message naming the engagement
- **Protected paths.** Use this exact wording:
  > **Do not rewrite delivered stakeholder briefs or delivered app behavior without confirmation. Status/path corrections, required engagement index updates, and integration-only package metadata updates are allowed when they are part of the active engagement cleanup.**

  Then list the paths the rule covers: [docs/briefs/](docs/briefs/), [docs/archive/](docs/archive/), [docs/standards/visibility.md](docs/standards/visibility.md), [apps/marketing-site/](apps/marketing-site/), [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/), [packages/shared/](packages/shared/).
- **Preserving milestone work** — delivered engagements stay intact; new work goes into new folders (`uis/`, `services/`, future engagement homes) unless an explicit migration is documented in a brief.
- **Respecting repository boundaries** — `apps/` and `uis/` depend on `packages/`; never the reverse. Public-facing pages must comply with [docs/standards/visibility.md](docs/standards/visibility.md) sections 1–6 before merge. APIs go under `services/`.
- **`.agents/` rules and skills** — link to [.agents/rules/](.agents/rules/) and [.agents/skills/](.agents/skills/); explain that agents must apply any rule whose scope matches the files they are touching, and may invoke any skill that fits the task.

### 1.4 `.agents/rules/` — scoped agent rules

Create [.agents/](.agents/) with the structure the brief requires. Add `.agents/README.md` distinguishing the four overlapping folder names (see §1.8). Minimum: one development rule.

**`.agents/rules/public-ui-visibility.md`** (required)
- **Scope:** file-pattern based
- **Applies when:** any change touches `apps/marketing-site/**`, `uis/website/**`, or any future folder containing public-facing pages
- **Required behavior:** before producing the change, read [docs/standards/visibility.md](docs/standards/visibility.md); the change must comply with sections 1–6 (semantic HTML, WCAG 2.1 AA, SEO metadata, GEO formatting, E-E-A-T, Schema.org JSON-LD); verify single H1 per page, `<html lang>`, canonical link, OG + Twitter cards, JSON-LD parses, decorative-only ARIA not used where a native element suffices
- **Examples:** adding a marketing page, editing the lead-capture form, changing `<head>` metadata
- **Non-examples:** edits to backoffice views, edits to internal API surface, edits to `packages/shared` source

**`.agents/rules/preserve-delivered-engagements.md`** (also required by the brief's "preserving milestone work" criterion)
- **Scope:** always active
- **Required behavior:** mirrors the exact protected-paths wording from §1.3, including the allowed-exception clause for status/path corrections, engagement index updates, and integration-only package metadata edits during the active engagement.

### 1.5 `.agents/skills/<skill>/SKILL.md` — reusable agent skill

Create one verifiable, recurring skill.

**`.agents/skills/start-engagement/SKILL.md`**
- **Objective:** correctly initialize a new engagement `NN` so the repo, briefs, and memory bank stay coherent.
- **Inputs:** engagement number `NN`, short slug, stakeholder name, one-line summary, intended deliverable path.
- **Workflow (ordered):**
  1. Read [README.md](README.md), [AGENTS.md](AGENTS.md), [CLAUDE.md](CLAUDE.md), and all three [memory-bank/](memory-bank/) files
  2. Create `docs/briefs/NN-<slug>.md` from the stakeholder-voice template (Status, Background, Stakeholder Request, Assignment, What You're Building, Acceptance Criteria, Out of Scope)
  3. Add the row to [docs/briefs/README.md](docs/briefs/README.md) with status `⏳ Upcoming`
  4. Add the row to the [README.md](README.md) roadmap table
  5. Add the entry to "Where New Engagement Code Goes" in [CLAUDE.md](CLAUDE.md), pointing at the brief
  6. Update `memory-bank/progress.md`: move prior Active → Completed if applicable; mark the new engagement as Active
  7. If the deliverable path is known, scaffold the folder with a `README.md`
- **Expected output:** a new brief file, updated index rows in four orientation files, an updated `progress.md`, and (optionally) a scaffolded deliverable folder README.
- **Acceptance criteria:** the `SKILL.md` defines a single clear objective, required inputs, an ordered workflow, expected output, and explicit acceptance criteria; the criteria reference concrete files (the brief, the four index files, `memory-bank/progress.md`).
- **Verification method:** open `SKILL.md` and confirm each required section is present and concrete. The skill is verified by static inspection of `SKILL.md` only — **do not** create a fake `99-dry-run` engagement; that would mutate the repo.

### 1.6 `uis/` workspace + `uis/website` public site

Create [uis/](uis/) at the repo root with a `uis/README.md` explaining: this is the forward-looking home for Next.js + TypeScript user interfaces (public and internal). [apps/](apps/) remains the home of delivered historical apps and is not being migrated in this engagement.

**`uis/website` — Next.js + TypeScript public website (React component refactor of Milestone 1)**

This is a React + TypeScript refactor, not a static copy. The output is a component-based Next.js app whose rendered HTML preserves the existing public-facing surface (sections, copy intent, SEO/GEO metadata, JSON-LD, accessibility, robots/sitemap/llms behavior).

- Scaffold Next.js App Router, TypeScript **strict mode**, Tailwind CSS, ESLint defaults.
- Add `uis/website/README.md` covering purpose, dev command, env vars, deployment notes; note that lead-form persistence is deferred to Engagement 5.
- Refactor sections from [apps/marketing-site/index.html](apps/marketing-site/index.html) into reusable React components. Required sections (confirmed from the current HTML):
  - Header / primary nav with language toggle
  - Hero (`#home`)
  - Services (`#services`)
  - Coverage (`#coverage`) — US + Spain operational addresses
  - Benefits (`#benefits`) — "Why TrackFlow"
  - FAQ (`#faq`) — FAQPage JSON-LD eligible
  - Contact (`#contact`) — lead-capture entry point
  - Footer with copyright, links, "updated date"
- Refactor `application.html` → `app/application/page.tsx` (lead-capture form). Refactor `privacy.html` → `app/privacy/page.tsx`.
- Refactor validation from [apps/marketing-site/assets/js/validation.js](apps/marketing-site/assets/js/validation.js) into a typed React form. Preserve every field validator (company name, contact, email, phone, URL, country, product type, volume, services, 3PL status, comments, privacy policy), the live character counter, and the low-volume warning behavior. Bilingual strings (current `window.TRANSLATIONS`) move into a typed translations module.
- **Lead-form submission target:** no real backend. The form validates and renders a local success state. This is final for Engagement 04.
- **Visual identity:** **Junecoast** palette via Tailwind tokens. Do **not** carry forward the `--tf-slate-*` / `--tf-gold-*` block from [apps/marketing-site/assets/css/styles.css](apps/marketing-site/assets/css/styles.css) — those tokens are stale and overridden. Leave the marketing site's CSS untouched.
- **Language toggle:** preserve the existing client-side EN/ES toggle from the static site. Typed `Locale = "en" | "es"`; current `window.TRANSLATIONS` strings are migrated into typed React/TypeScript content modules (e.g. `content/services.en.ts` + `content/services.es.ts`); toggle state persists in `localStorage`; switching the toggle updates `document.documentElement.lang`. No separate Spanish routes and no hreflang yet — both stay deferred per [docs/standards/visibility.md](docs/standards/visibility.md) and are tracked as follow-up #7.
- **SEO / GEO / Schema / accessibility behavior preserved end-to-end:**
  - Next.js `metadata` API for title, description, canonical, Open Graph, Twitter Card per route
  - Single H1 per page; semantic landmarks (`<header>`, `<main>`, `<footer>`); skip-to-content link
  - JSON-LD blocks for Organization (site-wide), WebPage (per route), FAQPage (on FAQ), ContactPage (on contact)
  - `<html lang>` attribute updates on locale switch; dedicated localized routes + hreflang remain deferred per [docs/standards/visibility.md](docs/standards/visibility.md)
  - `public/robots.txt`, `public/sitemap.xml`, `public/llms.txt` carried over (sitemap regenerated for Next routes)
- **Strict TypeScript types (required):**
  - `LeadFormData` — every field, optional vs. required modeled accurately; discriminated unions where validation branches on values (e.g., volume buckets)
  - `LeadFormErrors` — `Partial<Record<keyof LeadFormData, string>>`
  - `Locale` — `"en" | "es"`; both locales are active (EN/ES toggle behavior preserved)
  - `Translation` — typed shape mirroring the current `TRANSLATIONS` so missing keys are compile errors
  - `NavItem`, `FAQItem`, `ServiceCard`, `CoverageRegion`, `BenefitCard` — content shapes
  - `OrganizationSchema`, `WebPageSchema`, `FAQPageSchema`, `ContactPageSchema` — JSON-LD payload types
  - Shared UI prop types co-located with components
- **Component layout (initial proposal, all inside `uis/website/`):**
  - `components/layout/SiteHeader.tsx`, `SiteFooter.tsx`, `LanguageToggle.tsx`, `SkipToContent.tsx`
  - `components/sections/Hero.tsx`, `Services.tsx`, `Coverage.tsx`, `Benefits.tsx`, `FAQ.tsx`, `ContactCTA.tsx`
  - `components/forms/LeadForm.tsx` + field primitives (`TextField.tsx`, `SelectField.tsx`, `CheckboxField.tsx`, `CharacterCounter.tsx`)
  - `components/seo/JsonLd.tsx` (typed wrapper)
  - `content/` for typed content data (e.g., `services.en.ts`, `faq.en.ts`) — additions become content-only edits
- **Delivered Engagement 1 stays intact:** [apps/marketing-site/](apps/marketing-site/) is not modified.

### 1.7 `uis/backoffice` internal app

- Scaffold a second Next.js + TypeScript app at [uis/backoffice/](uis/backoffice/), strict mode, Tailwind. Add `uis/backoffice/README.md`; note that authentication is deferred to Engagement 5.
- **No auth.** Build the internal shell without a login screen. This is final for Engagement 04.
- **Shared layout** (header, side nav, content area) using strict-typed React components.
- **Visible integration of `packages/shared` (required):** an Inventory + Carrier Scoring view that consumes `@repo/shared-types` carrier scoring + shipping cost utilities and renders, for example, a small table of seeded shipments scored by the existing logic. Seed data lives in `uis/backoffice/content/` or `uis/backoffice/lib/seed.ts`. The import must be `import { … } from "@repo/shared-types"` — no relative `../../packages/shared/...` paths.
- **Visual identity:** **Junecoast** palette via Tailwind tokens (same as `uis/website` and [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/)).
- **Strict TypeScript types** for navigation items, the inventory/carrier view's view-model, and any UI prop types. Reuse domain types from `@repo/shared-types`; do not redefine them.

### 1.8 `services/` boundary

Create [services/](services/) at the repo root containing only a `README.md`:
- Reserved for future TrackFlow APIs and backend services (Engagement 5+)
- No services exist yet; do not place UI or shared library code here
- Future subfolders correspond to discrete services (e.g., `services/central-api/`)
- Not yet a workspace member; will be added to root `workspaces` when the first service lands

### 1.9 Documenting the four overlapping folder names

Add to [CLAUDE.md](CLAUDE.md) (and mirror in [AGENTS.md](AGENTS.md) and `.agents/README.md`) a section titled **"Coding-agent infrastructure vs. product agents"** with this table:

| Folder | Audience | Purpose |
|---|---|---|
| [.agents/](.agents/) | Coding agents working in *this repo* | Configuration: scoped rules + reusable workflows (skills) for *how to maintain this codebase* |
| [.agents/skills/](.agents/skills/) | Coding agents | Reusable repo-maintenance workflows (e.g. `start-engagement`) |
| [agents/](agents/) | TrackFlow customers / operations | **Product** AI agents the company ships in later engagements (e.g. support bot, returns triage) |
| [skills/](skills/) | TrackFlow product agents | Reusable **product** capabilities those agents call (e.g. code-review, data-analysis, research) |

Also extend the navigation table in [CLAUDE.md](CLAUDE.md) with rows for `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/`, and `services/`; and add an entry for Engagement 4 in "Where New Engagement Code Goes."

### 1.10 Cleanup of stale references and accidental state

- **Stale `apps/uis/` references** — [apps/talent-pipeline-tracker/spec.md](apps/talent-pipeline-tracker/spec.md) still uses `apps/uis/` at lines 41, 53, and 252. Update each occurrence to `apps/talent-pipeline-tracker/`. **Path correction only — no other edits.** Leave the two intentional mentions in [docs/briefs/04-ai-driven-engineering.md](docs/briefs/04-ai-driven-engineering.md) (lines 155, 208) untouched — they describe the rename itself.
- **Remove root `.claude/` from the repo:**
  - **Confirmed:** `.claude/worktrees/elated-mccarthy-e790cf` is tracked by Git as a **gitlink** (mode `160000`), not bound in `.gitmodules`. It's an accidental embedded-repo entry.
  - Cleanup: (1) `git rm --cached .claude/worktrees/elated-mccarthy-e790cf` to detach the gitlink from the index without disturbing the on-disk worktree directory; (2) remove the on-disk `.claude/` directory at the repo root (it's tool-generated state, not TrackFlow architecture); (3) commit the index change.
- **Update [.gitignore](.gitignore):** add a new "AI tooling state" block at the bottom containing `.claude/`, grouped alongside the existing `# Vercel` and `# Coverage` sections.

### 1.11 Engagement documentation maintenance

Per the existing rule in [CLAUDE.md](CLAUDE.md) (and now [AGENTS.md](AGENTS.md)), update these together:

- **At start of implementation** — all four index entries stay at `⏳ Upcoming`. Do not flip anything yet.
- **Mid-implementation** — once meaningful infrastructure (memory bank, workspaces, `uis/`) lands, flip status to `🚧 In progress` in [README.md](README.md), [docs/briefs/README.md](docs/briefs/README.md), [docs/briefs/04-ai-driven-engineering.md](docs/briefs/04-ai-driven-engineering.md) `## Status`, and `memory-bank/progress.md`.
- **At PR time, after every §4 acceptance criterion passes** — flip to `✅ Delivered`. Update [README.md](README.md) "What's Been Built" with the Engagement 4 entry. Update [CLAUDE.md](CLAUDE.md) "Where New Engagement Code Goes" to point at the delivered paths. Update the architecture tree in [README.md](README.md) to match §5 below.
- New folders (`memory-bank/`, `.agents/`, `uis/`, `uis/website/`, `uis/backoffice/`, `services/`) each get a README created during the work, not at PR time.

---

## 2. Optional / Follow-up Recommendations

Explicitly out of scope for Engagement 04 — none of these defer required workspace setup. Log under "Open decisions / known risks" in `memory-bank/progress.md`.

1. **Pin framework versions.** [apps/talent-pipeline-tracker/package.json](apps/talent-pipeline-tracker/package.json) pins `next`, `react`, `typescript` to `"latest"`. Replace with concrete ranges. Apply the same discipline to the new `uis/*` apps from the start of their scaffolds.
2. **Minimal CI.** Single `.github/workflows/ci.yml` running `npm install` + `npm run type-check` + `npm run build --workspaces --if-present`.
3. **Root `tsconfig.base.json`** with `strict: true` that each package/app extends. Prevents drift across engagements.
4. **Vitest scaffolds.** `uis/backoffice` to cover the `@repo/shared-types` integration view; `uis/website` to cover form validation and JSON-LD payload shape; `packages/shared` to cover validations + collections.
5. **Consolidate Junecoast tokens into a package.** A new `packages/design-tokens/` (or extending [packages/tailwind-config/](packages/tailwind-config/)) owning the `--jc-*` palette, consumed by `uis/website`, `uis/backoffice`, and (eventually) [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/). For Engagement 04 the three apps each carry their own Tailwind config + identical Junecoast values; consolidation is a small future refactor.
6. **Marketing-site retirement plan.** Once `uis/website` reaches parity, decide whether [apps/marketing-site/](apps/marketing-site/) is archived in [docs/archive/](docs/archive/) or kept as a historical reference. The brief explicitly does not require removal.
7. **Hreflang + dedicated Spanish routes.** The client-side EN/ES toggle is already preserved in Engagement 04. Still deferred per [docs/standards/visibility.md](docs/standards/visibility.md): dedicated localized routes (e.g. `/es/...`) and `hreflang` link tags. The `Locale` type and routing structure in `uis/website` are shaped so the future engagement is additive (new routes + alt-link tags) rather than a refactor.
8. **Lead-form persistence and backoffice auth.** Both deferred to Engagement 5 by decision in §1.0. When the central API lands, wire the form to a real endpoint and the backoffice to a real auth layer.

---

## 3. Risks

All scope decisions are locked in §1.0; this section is implementation risks only.

- **Workspace-adoption migration risk.** Adding the root `package.json` changes how `npm install` resolves packages for the existing workspace members ([apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/) and [packages/tailwind-config/](packages/tailwind-config/) both currently have their own lockfiles). Mitigation: after the root workspace is in place, delete every nested workspace lockfile (per §1.1), run `npm install` at the root, and verify `npm run dev` and `npm run build` still pass in [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/) and that `packages/tailwind-config/` still builds. If peer-dep complaints surface, fix them by adjusting versions — **do not** revert workspace adoption (it is required Engagement 04 work, not a tradeoff). Captured in §4.
- **`packages/shared` exposing `.ts` source.** Setting `"main": "src/index.ts"` works for consumers that transpile TS themselves (Next, via `transpilePackages`). A future plain-Node consumer in `services/` would need either a build step in `packages/shared` or its own transpiler. Decision: keep zero-build now; document the constraint in `packages/shared/README.md`; revisit when `services/` lands.
- **Junecoast token drift.** Three apps each own a Tailwind config containing the same Junecoast values. Drift over time is a real risk; mitigated by follow-up #5.
- **`apps/talent-pipeline-tracker/spec.md` line-number stability.** The plan references lines 41, 53, 252. If the file is edited before implementation, line numbers shift — implementation should `grep "apps/uis/"` rather than rely on line numbers.
- **`.claude/` gitlink.** Confirmed by `git ls-files --stage .claude` returning a `160000` entry. A plain `rm -rf .claude/` would leave the gitlink in the index — `git rm --cached` is required first (captured in §1.10).

---

## 4. Verification Steps

Run after implementation, before opening the PR. Engagement 04 is not marked `✅ Delivered` until every item below passes.

**Workspace + package wiring**
- `cat package.json` shows `"private": true` and `"workspaces": ["apps/*", "packages/*", "uis/*"]`
- `cat .nvmrc` returns exactly `22`
- `npm install` at the root succeeds; a single root `package-lock.json` exists
- `find . -maxdepth 4 -name package-lock.json -not -path "*/node_modules/*"` returns **only** `./package-lock.json` — no nested lockfiles in `apps/talent-pipeline-tracker/`, `packages/tailwind-config/`, `uis/website/`, or `uis/backoffice/`
- `node -e "console.log(require.resolve('@repo/shared-types'))"` resolves from `uis/backoffice` and from the repo root (`uis/website` does not consume `@repo/shared-types` and is not part of this check)
- `npm run build --workspaces --if-present` succeeds across all workspace members
- [apps/marketing-site/](apps/marketing-site/) is unchanged on disk; [apps/talent-pipeline-tracker/](apps/talent-pipeline-tracker/) still runs `npm run dev` and `npm run build` cleanly under the new workspace
- `git diff --stat packages/shared/src/types packages/shared/src/utils` is empty — existing business logic and type files are untouched; only the new `packages/shared/src/index.ts` barrel and `packages/shared/package.json` metadata appear in the diff for [packages/shared/](packages/shared/)

**Memory bank + agent infrastructure**
- `ls memory-bank/` shows `projectbrief.md`, `techContext.md`, `progress.md`
- Spot-read each file: TrackFlow-specific content; `techContext.md` lists npm workspaces + `@repo/shared-types` consumption as current state; `progress.md` **does not** list "no root workspace tooling" or "`@repo/shared-types` not consumed" as open risks
- `ls AGENTS.md .agents/rules/ .agents/skills/` confirms file + ≥1 rule + ≥1 `SKILL.md`
- Open `AGENTS.md`: startup reading list present; pre-commit workflow has ≥4 ordered steps; protected-paths section uses the exact §1.3 wording (including the allowed-exception clause for status/path corrections, engagement index updates, and integration-only package metadata updates); cross-reference to [CLAUDE.md](CLAUDE.md) present
- Open [CLAUDE.md](CLAUDE.md): top defers to `AGENTS.md` for cross-agent rules; no duplicated rule statements
- Open `.agents/skills/start-engagement/SKILL.md`: objective, inputs, ordered workflow, expected output, acceptance criteria, and verification method all present and concrete. **Verification is a static read of `SKILL.md` only — do not create a fake engagement to test the skill.**

**Rename + stale-reference cleanup**
- `grep -rn "apps/uis" . --include="*.md" --include="*.ts" --include="*.tsx" --include="*.json"` returns **only** the two intentional matches in [docs/briefs/04-ai-driven-engineering.md](docs/briefs/04-ai-driven-engineering.md)
- `git ls-files .claude` returns empty; `git ls-files --stage | grep '^160000'` returns empty (no orphan gitlinks)
- `grep -n "^\.claude/" .gitignore` returns a match
- The on-disk `.claude/` directory at the repo root is absent

**`uis/website`**
- `cd uis/website && npm run dev` — site loads at `http://localhost:3000`
- Visually confirm sections render: Hero, Services, Coverage, Benefits, FAQ, Contact, plus header/footer/skip-to-content/lang toggle
- Routes resolve: `/`, `/application`, `/privacy`
- `npm run build` succeeds with strict TS (no `any` introduced)
- Visibility spot-check ([docs/standards/visibility.md](docs/standards/visibility.md) §1–6): view source of `/` shows exactly one `<h1>`, `<html lang>`, canonical link, OG + Twitter meta, parseable JSON-LD blocks (Organization + WebPage + FAQPage)
- Lead form: empty submission triggers every original validator from `validation.js`; valid submission renders a local success state (no network call); character counter updates live; low-volume warning fires for 0–100/mo
- `public/robots.txt`, `public/sitemap.xml`, `public/llms.txt` served and reflect the new routes
- `grep -rn "tf-slate\|tf-gold" uis/website` returns nothing — stale palette tokens did not propagate

**`uis/backoffice`**
- `cd uis/backoffice && npm run dev` — app loads with shared layout
- `grep -rn "@repo/shared-types" uis/backoffice` returns the integration imports
- `grep -rn "packages/shared" uis/backoffice` returns nothing — no relative source paths into `packages/shared/src/`
- The rendered backoffice integration view displays values **produced by imported Engagement 2 utilities** (carrier scoring / shipping cost) using seeded data in `uis/backoffice/content/` or `uis/backoffice/lib/seed.ts`; this is verified visually without mutating `packages/shared`
- `npm run build --workspace uis/backoffice` succeeds with strict TS

**Documentation coherence**
- [README.md](README.md) roadmap row 04 status accurate at the moment of the PR; architecture tree matches §5 below
- [docs/briefs/README.md](docs/briefs/README.md) row 04 status + delivered code paths updated
- [docs/briefs/04-ai-driven-engineering.md](docs/briefs/04-ai-driven-engineering.md) `## Status` updated
- [CLAUDE.md](CLAUDE.md) "Where New Engagement Code Goes" entry for Engagement 04 present; navigation table includes new top-level folders; the four-folder distinction table from §1.9 is present
- Every new top-level folder (`memory-bank/`, `.agents/`, `uis/`, `uis/website/`, `uis/backoffice/`, `services/`) has a README

**End-to-end**
- One PR opened with the full change set, linking the brief, the memory bank entry, and §4 verification results

---

## 5. Final Architecture (post-Engagement 04)

```text
trackflow/
├── AGENTS.md                       # Cross-agent operating guide (all agents)
├── CLAUDE.md                       # Claude-specific orientation; defers to AGENTS.md
├── README.md
├── .nvmrc                          # Pinned Node version
├── package.json                    # private: true; workspaces: apps/*, packages/*, uis/*
├── package-lock.json               # Authoritative root lockfile
├── .gitignore                      # Includes .claude/ under "AI tooling state"
│
├── memory-bank/                    # Persistent project context for coding agents
│   ├── projectbrief.md             # TrackFlow business, stakeholders, objectives
│   ├── techContext.md              # Stack, architecture, decisions, constraints
│   └── progress.md                 # Completed / Active / Planned / Open risks
│
├── .agents/                        # Coding-agent infrastructure (CONFIG for THIS repo)
│   ├── README.md                   # Distinguishes .agents/ vs agents/, etc.
│   ├── rules/
│   │   ├── public-ui-visibility.md
│   │   └── preserve-delivered-engagements.md
│   └── skills/
│       └── start-engagement/
│           └── SKILL.md
│
├── apps/                           # Delivered historical apps (preserved)
│   ├── README.md
│   ├── marketing-site/             # Engagement 1 — static corporate site (unchanged)
│   └── talent-pipeline-tracker/    # Engagement 3 — recruiting app (unchanged)
│
├── uis/                            # Forward-looking UI workspace (Engagement 04+)
│   ├── README.md
│   ├── website/                    # Engagement 04 — Next.js + TS public site
│   │   ├── app/                    # App Router (/, /application, /privacy)
│   │   ├── components/             # layout/, sections/, forms/, seo/
│   │   ├── content/                # Typed content data
│   │   └── public/                 # robots.txt, sitemap.xml, llms.txt
│   └── backoffice/                 # Engagement 04 — Next.js + TS internal shell
│       ├── app/                    # App Router
│       ├── components/             # Layout + view components
│       └── lib/                    # Seed data; consumes @repo/shared-types
│
├── packages/                       # Shared TypeScript libraries
│   ├── README.md
│   ├── shared/                     # Engagement 2 — @repo/shared-types
│   │   ├── src/
│   │   │   ├── index.ts            # NEW: re-exports ./types + ./utils
│   │   │   ├── types/              # Unchanged business types
│   │   │   └── utils/              # Unchanged business utilities
│   │   └── package.json            # main/types point to src/index.ts
│   └── tailwind-config/            # Tailwind build for apps/marketing-site
│
├── services/                       # Reserved for future APIs (Engagement 5+)
│   └── README.md                   # No services yet; not yet a workspace member
│
├── agents/                         # PRODUCT AI agents for TrackFlow (Engagement 8)
│   ├── README.md
│   ├── _template/
│   └── tools/
│
├── skills/                         # PRODUCT capabilities for TrackFlow agents
│   ├── README.md
│   ├── _template/
│   ├── code-review/
│   ├── data-analysis/
│   └── research/
│
├── data/                           # Data engineering (Engagement 6)
├── workflows/                      # n8n automations (Engagement 9)
├── scripts/                        # Repo-wide utilities
├── resources/                      # Non-code shared resources
└── docs/
    ├── README.md
    ├── briefs/                     # Stakeholder briefs (per engagement)
    ├── standards/                  # visibility.md and future cross-cutting standards
    └── archive/
```

Relationship summary:

- **`apps/`** — delivered historical apps. Preserved as-is in this engagement.
- **`uis/`** — forward-looking UI workspace. New public-facing and internal Next.js + TypeScript apps land here.
- **`services/`** — reserved boundary for future backend services and APIs.
- **`memory-bank/`, `AGENTS.md`, `.agents/`** — coding-agent infrastructure for maintaining *this repo*. Read by all agents at the start of every session.
- **`agents/`, `skills/`** — product AI agents and product capabilities for *TrackFlow's business* in later engagements. Distinct architectural concern from `.agents/`.
- **`packages/shared`** — Engagement 2 TypeScript business logic. Consumed in this engagement by `uis/backoffice` via `@repo/shared-types` over npm workspaces.
