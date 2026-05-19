# `apps/uis/`

Internal TrackFlow talent pipeline tracker for the Executive Assistant search at Zaragoza HQ.

## Status

Delivered in Engagement 3.

## Purpose

- Replace the shared recruiting spreadsheet with a focused internal tool
- Give Ana's team one place to review candidates, update status and stage, and preserve interview notes
- Consume the existing TrackFlow recruiting API directly from the browser

## Key Files

- `app/page.tsx` - Candidate list
- `app/candidates/new/page.tsx` - Candidate registration
- `app/candidates/[id]/page.tsx` - Candidate detail, editing, and notes
- `components/` - UI and feature components
- `lib/api.ts` - Native fetch wrappers for the recruiting API
- `lib/labels.ts` - Human-readable labels for API enum values
- `tailwind.config.ts` - App-owned Junecoast theme tokens
- `spec.md` - Authoritative implementation spec

## Local Development

From this folder:

```bash
npm run dev
```

Then open `http://localhost:3000`.

## Environment

Create `.env.local` from `.env.example` when you need to point at a different API:

```env
NEXT_PUBLIC_API_URL=https://playground.4geeks.com/tracker/api/v1
```
