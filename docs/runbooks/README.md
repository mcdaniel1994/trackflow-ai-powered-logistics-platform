# `docs/runbooks/`

Operational runbooks for deploying, operating, and recovering TrackFlow services. A runbook is a
step-by-step operational procedure — distinct from a **standard** (`docs/standards/`, the rules code
must follow) and a **brief** (`docs/briefs/`, engagement scope).

**Status:** The Vercel frontend procedure is partial, while the Coolify backend
and Back Office deployment plus Supabase role/migration procedure are
production-verified. Repository-side approval-gated SHA deployment and manual
workflow rollback are implemented; their first live run and rollback drill
remain outstanding.

---

## Purpose & Structure

- One runbook per operational procedure, named `topic.md` (kebab-case).
- Each runbook should state: what it covers, prerequisites/access, the step-by-step procedure,
  verification, rollback, and known gaps.
- Distinguish **verified** facts (evidenced in this repo) from **unverified** platform
  configuration (e.g. Vercel dashboard settings) so readers know what is confirmed.

## Index

| Runbook | Status | Scope |
|---|---|---|
| [frontend-vercel-deployment.md](frontend-vercel-deployment.md) | Partial (gaps noted) | How the public website is built and deployed via Vercel |
| [backend-coolify-deployment.md](backend-coolify-deployment.md) | Production verified; automated workflow awaits first live run | Coolify order, automated SHA deployment, verification, troubleshooting, credential rotation, and rollback |
| [supabase-migrations.md](supabase-migrations.md) | Production migration verified; future changes approval-gated | Two-role security rationale, verified role setup, disposable-data waiver, migration, and recovery |
| [identity-tinydb-backup-restore.md](identity-tinydb-backup-restore.md) | Deferred by portfolio waiver | Future Identity backup, isolated restore, revocation, and key rotation |
| [telemetry-inventory.md](telemetry-inventory.md) | Living reference | Every telemetry signal: implemented today vs. Engagement 6 vs. deferred, with fields, storage, retention, access, and evidence |
| [operations-feed.md](operations-feed.md) | Portfolio-production | The live operations feed worker, its single-writer/kill-switch safety, telemetry enablement, and the database-size guard that bounds Supabase Free |

## Current Deployment Process (summary)

- **Public website (`uis/website/`)** is deployed via **Vercel** — the live demo at
  `trackflow-ai-powered-logistics-plat.vercel.app` is referenced in the root `README.md`. Build is
  Next.js (`next build`/`next start`); `@vercel/analytics` is wired in the website. Project settings
  (env vars, branch mapping, build config) live in the Vercel dashboard, not in this repo (no
  `vercel.json` is committed). Details and the verified/unverified split are in
  [frontend-vercel-deployment.md](frontend-vercel-deployment.md).
- **Back office (`uis/backoffice/`)** is production-verified through Coolify at
  `https://backoffice.forgehub.cloud`.
- **Identity and Central API** run privately in the same Coolify Compose stack.
  Neither service has a public domain or host-port mapping.
- **Eligible Back Office/backend merges to `main`** now pass reusable release
  checks, publish three immutable GHCR images, wait for GitHub `production`
  approval, and then deploy the exact SHA through Coolify. Manual dispatch of
  the same workflow is the rollback path.

## Known Gaps (no runbook yet — do not fabricate)

- A live rollback drill; the rollback procedure is documented but has not been
  executed against production.
- External uptime monitoring and centralized log shipping.
- Incident response (who responds, escalation, comms).
- Environment/secrets management procedure.
- Scheduled backups and restore drills are waived for the current disposable
  portfolio deployment; revisit before storing meaningful production data.

## Relationship to CI and Standards

- Quality gates that must pass before a deploy live in
  [`docs/standards/production-readiness.md`](../standards/production-readiness.md).
- Intended CI automation is described in [`../../.github/workflows/README.md`](../../.github/workflows/README.md).

## Implementation Checklist (follow-up)

- [x] Verify and document the Back Office deployment target.
- [x] Add and production-verify the backend service deployment runbook.
- [x] Add rollback steps to the backend deployment runbook.
- [x] Define and verify Identity, Central API, and Back Office health endpoints.
- [x] Add repository-side approval-gated SHA deployment and workflow rollback.
- [ ] Complete the first approved automated deployment and a separate live rollback drill.
- [ ] Add external uptime monitoring and a monitoring runbook.
- [ ] Write an incident-response runbook.
- [ ] Document environment/secrets management.
