# Runbook: Frontend Deployment (Vercel)

**Status:** Partial — documents what is verifiable in this repository. Vercel platform settings are
configured in the Vercel dashboard and are **not** committed here; those items are marked
*unverified* below and must be confirmed in the Vercel project before relying on them.

This runbook covers the **public website** (`uis/website/`). It does **not** cover the back office
or backend services — see [README.md](README.md) for why.

---

## Verified Facts (evidenced in this repository)

- A **public website** lives at [`uis/website/`](../../uis/website/) and is a Next.js app
  (`uis/website/next.config.ts`).
- It builds and runs with standard Next.js scripts — `next build` / `next start`
  (`uis/website/package.json`).
- It includes `@vercel/analytics` (`uis/website/package.json`), indicating Vercel hosting.
- The root `README.md` links a live demo at `trackflow-ai-powered-logistics-plat.vercel.app`.
- **No `vercel.json`** is committed anywhere in the repo, so deployment configuration is not
  source-controlled.

Taken together, the public website is deployed on Vercel and built from this repo's `uis/website/`.

## Unverified — Confirm in the Vercel Dashboard

These are **not** evidenced in the repository and must not be assumed:

- Which Git branch maps to the production deployment, and preview-branch behavior.
- The Vercel project name, team, and root-directory/monorepo settings (this is a workspace monorepo,
  so the project's "Root Directory" must point at `uis/website`).
- Build command and output settings as configured in Vercel (repo defaults are `next build`).
- Environment variables and secrets configured for the deployment.
- Custom domains beyond the `*.vercel.app` URL.
- **Whether the back office (`uis/backoffice/`) is also deployed.** There is no in-repo evidence
  (no `@vercel/analytics`, no committed config). Do not document it as deployed until confirmed.

## Deployment Procedure (current understanding)

> Confirm the *unverified* items above before treating these as authoritative.

1. Changes to `uis/website/` are merged to the production branch on GitHub.
2. Vercel detects the push and builds the project (`next build`) from the configured root directory.
3. Vercel promotes the build to the production URL; per-PR pushes get preview deployments.
4. `@vercel/analytics` reports traffic for the deployed site.

## Verification After Deploy

- Load the production URL and confirm the expected build/content is live.
- Check the Vercel deployment log for build success and no runtime errors.
- Confirm public-page requirements still hold — see
  [`docs/standards/visibility.md`](../standards/visibility.md).

## Rollback

- **Gap:** no rollback procedure is documented. Vercel supports promoting a previous deployment from
  the dashboard; the exact steps and ownership must be defined and added here.

## Known Gaps

- Rollback steps (above).
- No documented env/secrets management procedure.
- No CI gate in front of the Vercel deploy yet — see
  [`../../.github/workflows/README.md`](../../.github/workflows/README.md) for the intended
  PR/merge/Vercel interaction.
- Back office and backend services deployment — see [README.md](README.md).

## Related

- [`docs/runbooks/README.md`](README.md) — runbook index and gaps.
- [`docs/standards/production-readiness.md`](../standards/production-readiness.md) — pre-deploy gates.
- [`docs/standards/visibility.md`](../standards/visibility.md) — public-page requirements.
