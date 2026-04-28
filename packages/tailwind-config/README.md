# `packages/tailwind-config/`

Shared Tailwind CSS build setup for TrackFlow apps.

## Purpose

Owns the Tailwind input CSS and build commands that compile site styles. Keeps Tailwind configuration centralized so multiple apps can consume the same design tokens.

## Key Files

- `src/input.css` — Tailwind directives and custom layers
- `tailwind.config.js` — Tailwind configuration (theme, content globs)
- `package.json` — `build` and `watch` scripts

## Consumers

- `apps/marketing-site/` — compiled output written to `apps/marketing-site/assets/css/styles.css`

## Usage

From this folder:

```bash
npm run build    # one-shot minified build
npm run watch    # rebuild on change during development
```
