# `docs/runbooks/`

Operational runbooks for deploying, operating, and recovering TrackFlow services. A runbook is a
step-by-step operational procedure — distinct from a **standard** (`docs/standards/`, the rules code
must follow) and a **brief** (`docs/briefs/`, engagement scope).

**Status:** Early scaffolding. Only the frontend deployment runbook exists today, and it documents a
partly Vercel-managed process with known gaps (below). Add runbooks as real operational procedures
become verifiable — do not document procedures that do not exist.

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
| [backend-coolify-deployment.md](backend-coolify-deployment.md) | Prepared; production unverified | Coolify order, verification, and rollback |
| [supabase-migrations.md](supabase-migrations.md) | Role bootstrap verified; migrations approval-gated | Two-role security rationale, verified role setup, disposable-data waiver, migration, and recovery |
| [identity-tinydb-backup-restore.md](identity-tinydb-backup-restore.md) | Deferred by portfolio waiver | Future Identity backup, isolated restore, revocation, and key rotation |

## Current Deployment Process (summary)

- **Public website (`uis/website/`)** is deployed via **Vercel** — the live demo at
  `trackflow-ai-powered-logistics-plat.vercel.app` is referenced in the root `README.md`. Build is
  Next.js (`next build`/`next start`); `@vercel/analytics` is wired in the website. Project settings
  (env vars, branch mapping, build config) live in the Vercel dashboard, not in this repo (no
  `vercel.json` is committed). Details and the verified/unverified split are in
  [frontend-vercel-deployment.md](frontend-vercel-deployment.md).
- **Back office (`uis/backoffice/`)** deployment is **not confirmed** by anything in this repo
  (no `@vercel/analytics`, no committed deploy config). Do not assume it is deployed until verified.
- **Backend services** have a repository-defined Coolify Compose path that has
  not yet been executed or production-verified.

## Known Gaps (no runbook yet — do not fabricate)

- Production verification of the prepared backend deployment and rollback.
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

- [ ] Verify and document the back-office deployment target (or confirm it is not deployed).
- [ ] Add a backend service deployment runbook once a hosting target is chosen.
- [ ] Add rollback steps to each deployment runbook.
- [ ] Define and document health-check endpoints, then a monitoring runbook.
- [ ] Write an incident-response runbook.
- [ ] Document environment/secrets management.
