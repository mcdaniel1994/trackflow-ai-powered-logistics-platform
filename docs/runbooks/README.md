# `docs/runbooks/`

Operational runbooks for deploying, operating, and recovering TrackFlow services. A runbook is a
step-by-step operational procedure — distinct from a **standard** (`docs/standards/`, the rules code
must follow) and a **brief** (`docs/briefs/`, engagement scope).

**Status:** The Vercel frontend procedure is partial, while the Coolify backend
and Back Office deployment plus Supabase role/migration procedure are
production-verified. Repository-side approval-gated SHA deployment and manual
workflow rollback are implemented. The first dedicated-Prefect live run exposed a documented
Coolify init-mount defect; its repository hotfix and Phase 6.1 were successfully deployed on July
28. The owner omitted the remaining Phase 6.1 exercises. Phase 6.2 is production-accepted. Phase
6.3 rollback drill one passed, after which the owner accepted the phase by explicit exception and
waived rollback drill two and the observation window without executing them. Phase 6.4 is approved
to begin, but its production mutations and time-gate exceptions remain separately owner-gated.

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
| [backend-coolify-deployment.md](backend-coolify-deployment.md) | SHA deployment verified; Phase 6.3 drill one passed | Approval-gated migration, SHA deployment, readiness/smoke verification, Compose incident recovery, and automatic image rollback |
| [supabase-migrations.md](supabase-migrations.md) | Hardened command verified locally; production credential rotation pending | Two-role setup, database CREATE grant, automated grants, disposable-data waiver, and recovery |
| [identity-tinydb-backup-restore.md](identity-tinydb-backup-restore.md) | Deferred by portfolio waiver | Future Identity backup, isolated restore, revocation, and key rotation |
| [telemetry-inventory.md](telemetry-inventory.md) | Living reference | Every telemetry signal: implemented today vs. Engagement 6 vs. deferred, with fields, storage, retention, access, and evidence |
| [operations-feed.md](operations-feed.md) | Portfolio-production | The live operations feed worker, its single-writer/kill-switch safety, telemetry enablement, and the database-size guard that bounds Supabase Free |
| [business-performance-pipeline.md](business-performance-pipeline.md) | Phase 6.3 owner-accepted by exception; Phase 6.4 approved to begin | Reporting authority, SQL rollups/reconciliation, idempotent database bootstrap, Prefect durability, operator triage, upgrade, recovery, and rollback |

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

- The Phase 6.3 computation-disable rollback drill was waived by owner exception and was not
  executed. The immutable-image rollback drill remains; the control-plane/safe-stale production
  drill passed on July 28.
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
- [x] Complete the approved Prefect hotfix redeployment.
- [x] Deploy and live-reconcile the Phase 6.2 shadow rollups.
- [x] Complete Phase 6.3 rollback drill one: control-plane outage and verified-stale serving.
- [x] Record Phase 6.3 rollback drill two and observation as waived, not passed, by owner exception.
- [ ] Complete Phase 6.4 measurement windows and executor verification without compressing evidence.
- [ ] Add external uptime monitoring and a monitoring runbook.
- [ ] Write an incident-response runbook.
- [ ] Document environment/secrets management.
