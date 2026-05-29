# `uis/website/`

Next.js + TypeScript public website for TrackFlow.

## Purpose

This app is the Engagement 4 component-based refactor of the delivered static marketing site in `apps/marketing-site/`. It preserves the public sections, bilingual client-side language toggle, visibility metadata, crawl assets, and lead-capture intent while moving future public website work into the `uis/` workspace.

## Local Development

```bash
npm run dev --workspace trackflow-website
```

The app runs on `http://localhost:3000` by default.

## Environment Variables

No environment variables are required for Engagement 4.

## Lead Form

The request-information form validates locally and renders a local success state. Persistence and API submission are deferred to Engagement 5.

## Deployment Notes

Deploy as a standard Next.js App Router project. The public crawl files live in `public/`, and route metadata is owned by the App Router metadata API.
