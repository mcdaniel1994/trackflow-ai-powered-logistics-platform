# `uis/backoffice/`

Next.js + TypeScript internal backoffice shell for TrackFlow.

## Purpose

This Engagement 4 app establishes the forward-looking home for internal company tools. The first view shows inventory and carrier scoring using `@repo/shared-types` through npm workspaces.

The Incident Report Processor subproject adds an internal CX route at `/incidents`. It uploads incident CSV exports to the FastAPI service in `services/incident-processor/` and displays aggregate metrics only.

The Supplier Directory subproject adds internal operations routes for supplier management:

- `/suppliers` - compact supplier directory dashboard for scanning and filtering suppliers.
- `/suppliers/new` - supplier registration form.
- `/suppliers/[id]` - supplier detail page with full read-only record details, rate updates, status suspend/reactivate controls, and a privileged contact-email reveal action.

These routes connect to the FastAPI + TinyDB service in `services/supplier-directory/`. The directory table shows only the `has_contact_email` signal, and raw contact email is revealed only from the supplier detail page after an explicit click.

The Talent Pipeline Tracker (Engagement 3) lives at `/talent` (list), `/talent/new` (registration), and `/talent/[id]` (detail, edit, notes), migrated from the retired standalone app in June 2026 (`docs/archive/talent-pipeline-tracker-retirement.md`). Its components live under `components/talent/` and its API client under `lib/talent/`.

## Local Development

```bash
npm run dev --workspace trackflow-backoffice
```

The app runs on `http://localhost:3000` by default.

## Authentication

No login screen ships in Engagement 4. Authentication is deferred to Engagement 5.

## Environment Variables

Optional:

- `NEXT_PUBLIC_INCIDENT_PROCESSOR_API_URL` - base URL for the incident processor API. Defaults to `http://localhost:8000`.
- `NEXT_PUBLIC_SUPPLIER_DIRECTORY_API_URL` - base URL for the supplier directory API. Defaults to `http://localhost:8001`.
- `NEXT_PUBLIC_TALENT_API_URL` - base URL for the talent pipeline backend. Defaults to the 4Geeks playground API. Kept separate from `NEXT_PUBLIC_API_URL` so the talent client and the incident client never point at each other's backend.

No customer emails should be rendered in the backoffice UI. Supplier contact emails are accepted by the create form for the local demo, but the `/suppliers` table must render only "Contact on file" from `has_contact_email`, never the raw email value. The `/suppliers/[id]` detail page may reveal the supplier contact email only through its explicit reveal control.
