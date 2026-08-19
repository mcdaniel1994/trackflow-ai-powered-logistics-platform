# `uis/website/`

Next.js + TypeScript public website for TrackFlow.

## Purpose

This app is the Engagement 4 component-based refactor of the delivered Engagement 1 static marketing site (originally `apps/marketing-site/`, retired June 2026 — see `docs/archive/marketing-site-retirement.md`). It preserves the public sections, bilingual client-side language toggle, visibility metadata, crawl assets, and lead-capture intent, and is now the sole home of TrackFlow's public website.

Mobile navigation is a header hamburger dropdown in `SiteHeader.tsx` (there is no fixed bottom bar). The hero renders a looping, muted, `playsInline` background video (`Hero.tsx`) with a mandatory `prefers-reduced-motion` still fallback that reuses the existing poster/JSON-LD PNG.

## Local Development

```bash
npm run dev --workspace trackflow-website
```

The app runs on `http://localhost:3000` by default.

## Environment Variables

- `NEXT_PUBLIC_BACKOFFICE_URL` - hosted Back Office login origin used by both
  desktop and mobile navigation. Defaults to `https://backoffice.forgehub.cloud`.

## Lead Form

The request-information form validates locally and renders a local success state. Persistence and API submission are deferred to Engagement 5.

## Deployment Notes

Deploy as a standard Next.js App Router project. The public crawl files live in `public/`, and route metadata is owned by the App Router metadata API.
