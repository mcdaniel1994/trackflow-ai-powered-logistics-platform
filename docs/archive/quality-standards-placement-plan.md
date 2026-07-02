# Archived Plan: Engineering Quality Standards — Documentation Placement

> **Archived June 2026.** This is the planning artifact that produced the engineering quality
> framework. It was approved (with clarifications) and implemented. Living documents are the
> standards in [`../standards/`](../standards/), the routing rule
> [`../../.agents/rules/testing-error-handling-ci.md`](../../.agents/rules/testing-error-handling-ci.md),
> the CI intent doc [`../../.github/workflows/README.md`](../../.github/workflows/README.md), and the
> runbooks in [`../runbooks/`](../runbooks/). Refer to those, not this snapshot. Per archive policy,
> this file is not updated.

**Outcome — files delivered:**

- Created standards: `docs/standards/testing.md`, `error-handling.md`, `observability.md`,
  `production-readiness.md`.
- Created agent rule: `.agents/rules/testing-error-handling-ci.md` (single routing rule).
- Created scaffolding: `.github/workflows/README.md` (no YAML), `docs/runbooks/README.md`,
  `docs/runbooks/frontend-vercel-deployment.md`.
- Updated: `docs/standards/README.md` (index + exceptions), `.agents/rules/README.md` (catalog),
  `AGENTS.md` and `CLAUDE.md` (discovery triggers + navigation).
- Approved adjustments applied: standards may link (not duplicate) to implementation/runbooks;
  coverage policy in `testing.md` with exact values deferred to config/CI; Vercel runbook separates
  verified facts from unverified dashboard config and does not assume back-office is deployed;
  general non-auth security folded into `production-readiness.md`.

---

## Context

TrackFlow needed a home for a reusable engineering quality framework distilled from recent audits
(test coverage, error handling, production readiness, CI/CD enforcement, AI-agent practices). The
goal was to place the content so it fit existing conventions, became the single source of truth, was
auto-discoverable by AI agents, and did not duplicate or fragment existing docs.

## Recommended Structure (as implemented)

```
docs/standards/
  testing.md                 (new)  test levels, coverage policy/ratcheting, local workflow
  error-handling.md          (new)  error patterns, API validation, safe responses, DB/external failures
  observability.md           (new)  logging, audit events, monitoring, never-log list
  production-readiness.md     (new)  release gates + general (non-auth) security
  README.md                  (upd)  index rows + Exceptions section
docs/runbooks/
  README.md                  (new)  purpose, Vercel summary, gaps, checklist
  frontend-vercel-deployment.md (new) verified vs unverified Vercel facts
docs/planning/                (—)   home for future TrackFlow-specific remediation plans
.agents/rules/
  testing-error-handling-ci.md (new) routing rule → 4 standards
  README.md                  (upd)  catalog row
.github/workflows/
  README.md                  (new)  intended CI architecture; no executable YAML yet
AGENTS.md / CLAUDE.md         (upd)  discovery triggers + navigation
```

## Source-of-Truth Strategy

Canonical source = `docs/standards/<topic>.md`. Everything else (agent rule, AGENTS.md, CLAUDE.md,
CI README, runbooks) links to standards rather than copying normative content. Catalog READMEs index
only. Linking is one-way (rules → standards), matching the existing auth/visibility pattern.

## Agent Discovery Strategy

Four layers: (1) CLAUDE.md startup reading + navigation; (2) AGENTS.md operating triggers (read by
non-Claude agents); (3) the scoped `.agents/rules/testing-error-handling-ci.md` routing rule that
maps work-type → standard and requires agents to report which standards they reviewed; (4)
point-of-work references. Agent files link to standards; they never inline the full text.

## Decisions That Were Approved

- Four grouped standards (not one mega-doc, not 11 fragments).
- CI + runbook scaffolding via README now; no placeholder workflow YAML.
- Single routing rule named `testing-error-handling-ci.md`.
- Clean `topic.md` filenames (no `-rule` suffix).
- `docs/planning/` for future TrackFlow-specific remediation plans.
- Update `AGENTS.md`/`CLAUDE.md` for discovery.
- No standalone general `security.md`; non-auth security folded into `production-readiness.md`,
  auth-specific concerns continue to defer to `authentication-security-standard.md`.
