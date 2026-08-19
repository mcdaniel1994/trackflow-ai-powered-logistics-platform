# `uis/backoffice/`

Next.js + TypeScript internal backoffice shell for TrackFlow.

## Purpose

This Engagement 4 app establishes the forward-looking home for internal company tools. The first view shows inventory and carrier scoring using `@repo/shared-types` through npm workspaces.

The Centralized Incident Manager adds an internal operations route at `/incidents`.
It registers incidents through Central API, filters them by operational context,
enforces lifecycle transitions, and shows summary metrics. The former CSV
processor was retired after its import dependency moved into Central API.

The Supplier Directory subproject adds internal operations routes for supplier management:

- `/suppliers` - compact supplier directory dashboard for scanning and filtering suppliers.
- `/suppliers/new` - supplier registration form.
- `/suppliers/[id]` - supplier detail page with full read-only record details, rate updates, status suspend/reactivate controls, and a privileged contact-email reveal action.

These routes connect through the BFF to Central API's PostgreSQL supplier
domain. The directory table shows only the `has_contact_email` signal, and raw
contact email is revealed only from the supplier detail page after an explicit
click.

The Talent Pipeline Tracker (Engagement 3) lives at `/talent` (list), `/talent/new` (registration), and `/talent/[id]` (detail, edit, notes), migrated from the retired standalone app in June 2026 (`docs/archive/talent-pipeline-tracker-retirement.md`). Its components live under `components/talent/` and its API client under `lib/talent/`.

The Backoffice Inventory Management UI consumes Engagement 5 through a same-origin,
allowlisted BFF and leaves the original Inventory + Carriers dashboard at `/` intact:

- `/backoffice/inventory/products` - paginated products and computed stock.
- `/backoffice/inventory/orders/inbound` - receive stock.
- `/backoffice/inventory/orders/outbound` - record dispatches and confirmed losses.
- `/backoffice/inventory/orders` - read-only movement history.

Engagement 8 Phase 6 replaces `/agent-os` with an authenticated, responsive observability dashboard
over the Central API's self-hosted trace store. It lists and filters authoritative runs, preserves
the selected trace during auto-refresh, renders the exact ordered node path and safe tool metadata,
and shows only the trace store's redacted/truncated final-output summary. The read-only
`/api/agents` BFF has an explicit list/detail allowlist and replaces upstream error bodies with safe
status messages.

During the August 3 disposable local exercise, a fresh authenticated session returned successful
allowlisted reads for incidents, telemetry aggregates, reporting health, and Agent OS runs. This was
a local API smoke check rather than production evidence. The owner accepted Phase 6 and closed
Engagement 8 on August 3, 2026; production exposure and deployment remain separately gated.

Engagement 10 Part 1 replaces the RFP Desk's five-second list/detail polling with a same-origin
`fetch` + `ReadableStream` SSE client. It opens the owner-scoped stream before loading the
authoritative ticket snapshot, buffers arrivals during that read, merges without replacing
authoritative rows, and deduplicates by `ticket_id`. Network loss uses capped exponential backoff
with jitter; every reconnect repeats the snapshot recovery. New tickets receive a distinct notice
and highlighted row, while explicit Refresh/upload/decision reads remain available.

Engagement 10 Phase 4 reworks the home-page Ask AI surface into an accessible chat slide-over:
right-side drawer on larger screens, full-screen sheet on mobile, Escape/backdrop dismissal, focus
return, cleared inputs after send, and an Auto/Knowledge base/Ticket lookup route picker. The panel
creates an owner-scoped session, threads its `session_id` through the existing agent conversation,
surfaces the route actually used, and restores ordered 90-day history from the allowlisted
`/api/agents/chat/sessions` BFF paths. Phase 5 sends chat turns over the same-origin
`/realtime/chat/{session_id}` WebSocket, which carries the existing host-only cookie automatically.
The client queues until open, renders guarded answer deltas progressively, reconnects with capped
exponential backoff and jitter, replaces cached history with the authoritative persisted and active
generation snapshot, and supports both Stop and interrupt-with-new-input. No token is exposed to
browser JavaScript or a URL.

Engagement 10 browser implementation is complete and merged to `main` through PR #36. Phase 6
production rollout is deferred; this closeout does not claim the UI is enabled or deployed in
production.

## Local Development

```bash
npm run dev --workspace trackflow-backoffice
```

The app runs on `http://localhost:3000` by default.

## Authentication

Auth 2 protects the Back Office with a same-origin Next.js BFF:

- `/login` signs in through `services/identity/` and receives HttpOnly auth cookies through the Back Office origin.
- `/forgot-password` and `/reset-password` are public account-recovery pages that forward through the same-origin BFF to Auth 3 identity endpoints.
- `/account/profile` lets authenticated users update their display name.
- `/account/change-password` supports normal password changes and the temporary-password first-login flow.
- `/admin/users` lets admins create users, view/filter accounts, suspend, disable, reactivate, and revoke refresh sessions. New users receive an account setup email when identity email delivery is configured; the one-time temporary password remains visible once to the admin as a fallback.
- `app/api/*` route handlers proxy browser requests to Identity, Central API,
  and the talent API.

The browser calls only same-origin `/api/*` URLs plus the direct `/realtime/*` transport route. Tokens
are never stored in web storage; the real-time transport receives the HttpOnly access cookie
automatically, and state-changing requests forward the `trackflow_csrf` cookie value as
`X-CSRF-Token`.

Password-reset links are generated by `services/identity` from its `FRONTEND_BASE_URL` setting. The Back Office does not store reset tokens, decode JWTs in the browser, or hold email-provider secrets.

## Environment Variables

Server-only values used by the BFF:

- `IDENTITY_API_URL` - identity service URL. Defaults to `http://localhost:8002`.
- `TALENT_API_URL` - talent pipeline backend URL. Defaults to the 4Geeks playground API.
- `CENTRAL_API_URL` - Central API server URL. Defaults to `http://localhost:8003` to avoid Identity's local port 8002.
- `AUTH_COOKIE_SECURE` - set `false` only for local HTTP development; hosted deployments require HTTPS and secure cookies.
- `PUBLIC_WEBSITE_URL` - public TrackFlow website used by the login-page back link. Defaults to the current Vercel demo URL.

Do not expose service URLs or token material through `NEXT_PUBLIC_*` values.

The login page's demo-account controls only autofill the published demo credentials; they do not
create users or bypass Identity. Create those accounts only in an isolated demo Identity store with
disposable data, never in production.

No customer emails should be rendered in the backoffice UI. Supplier contact emails are accepted by the create form for the local demo, but the `/suppliers` table must render only "Contact on file" from `has_contact_email`, never the raw email value. The `/suppliers/[id]` detail page may reveal the supplier contact email only through its explicit reveal control.
