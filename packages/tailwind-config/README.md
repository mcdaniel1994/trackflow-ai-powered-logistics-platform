# `packages/tailwind-config/`

Shared Tailwind CSS build setup for TrackFlow apps.

## Purpose

Owns the Tailwind input CSS and build commands that compile site styles. Keeps Tailwind configuration centralized so multiple apps can consume the same design tokens.

## Key Files

- `src/input.css` — Tailwind directives and custom layers
- `tailwind.config.js` — Tailwind configuration (theme, content globs)
- `package.json` — build scripts (see "Scripts" below)

## Consumers

- `apps/marketing-site/` — delivered Engagement 1 CSS at `apps/marketing-site/assets/css/styles.css`. This is a protected, delivered artifact under the rules in [AGENTS.md](../../AGENTS.md).

## Scripts

- `npm run build` — protected-artifact guard. Workspace-wide loops such as `npm run build --workspaces --if-present` invoke this script, and it intentionally does **nothing** so the delivered marketing-site CSS is not overwritten as a side effect.
- `npm run build:marketing-site` — intentionally regenerates `apps/marketing-site/assets/css/styles.css` from `src/input.css`. Only run when the historical marketing site is genuinely being rebuilt. Do **not** run this during Engagement 04 verification, because the regenerated minified output drops the trailing `--tf-slate-*` / `--tf-gold-*` override block that the delivered file contains today.
- `npm run watch` — rebuild on change during development of the marketing site. Same caveat as `build:marketing-site` — only use when intentionally iterating on the historical marketing CSS.

## Usage

From this folder:

```bash
npm run build              # no-op guard; safe in workspace-wide loops
npm run build:marketing-site  # intentional rebuild of the delivered Engagement 1 CSS
npm run watch              # dev iteration on the marketing site
```
