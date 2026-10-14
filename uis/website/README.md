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
- `TALENT_API_URL` - server-only sandbox origin/API prefix, identical to Back Office's setting.
- `CAREERS_DEMO_ENABLED` - off by default; enables fictional applications after live contract verification.
- `PUBLIC_SUPPORT_ENABLED` - off by default; independent of employee chat.
- `SUPPORT_GATEWAY_URL` - server-only fixed HTTPS Back Office origin.
- `WEBSITE_GATEWAY_SECRET` - shared only by the three servers; never `NEXT_PUBLIC_*`.

Copy `.env.example` to an untracked local environment file. Provider keys stay in Central API.

## Customer demo (Engagement 11)

`/careers` offers three illustrative roles and a general application, bilingual demo disclosures,
sample fill and strict fictional-data validation. The same-origin submission route writes only
allowlisted fields to the existing talent sandbox. It validates received/pending/server timestamp
confirmation before returning an opaque candidate ID and rendering the authenticated detail link.
Ambiguous write outcomes are never retried automatically. No applicant database or uploads are added.

The site-wide TrackFlow Support panel keeps history in page memory, separates language from policy
country, and uses a fixed authenticated gateway to the private public-only knowledge endpoint. It
shows complete answers with loading/error states. Public history, tools and staff identity are absent
from the backend. Application/chat text is never included in telemetry.

The chat launcher stays above visible footer links and is compact on mobile. Greetings such as
"Hello" receive a static welcome without a country selection or paid AI call. Policy questions
remain gated; when disabled, the panel explains that policy answers have not been enabled yet.

Website tests mock upstreams. The cross-app local journey runs from the Back Office workspace:
`npm exec --workspace trackflow-backoffice playwright test -- --config playwright.customer-demo.config.ts`.
See [rollout and local verification](../../docs/runbooks/customer-demo.md) for feature flags,
single-instance limits, verified local live checks and remaining hosted checks.

October 14 owner-authorized preview: `http://127.0.0.1:3005`, with Careers and grounded public
policy answers enabled through ignored `.env.local`. Public indexing and the fictional live
application-to-Back-Office journey passed; hosted rollout is still deferred. `.env.example`
is a template and does not configure a running Next.js server.

## Lead Form

The request-information form validates locally and renders a local success state. Persistence and API submission are deferred to Engagement 5.

## Deployment Notes

Deploy as a standard Next.js App Router project. The public crawl files live in `public/`, and route metadata is owned by the App Router metadata API.
