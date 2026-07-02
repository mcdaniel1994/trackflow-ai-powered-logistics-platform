# Production-Readiness Standards

**Last reviewed:** June 2026  
**Next review due:** September 2026 (quarterly)

This file is the authority on the quality gates a change must clear to be considered production-ready,
and on the broader (non-authentication) security requirements that apply across the platform. It ties
the other quality standards together into a release checklist.

---

## Scope

Applies to every change merged toward `main` and any deployment. It defines *what* must be true
before release. *How* those gates are automated lives in the CI design at
[`../../.github/workflows/README.md`](../../.github/workflows/README.md); *how* deployments run lives
in [`../runbooks/`](../runbooks/). Authentication-specific security remains governed by
[authentication-security-standard.md](authentication-security-standard.md); this file references it for
auth concerns and covers general security below.

---

## How AI Coding Agents Should Use This File

- Read this file before finishing a change, wiring CI, or preparing a release.
- Treat the [Release Gates](#1-release-gates) as a checklist; do not call work "done" until they pass.
- For auth-related security, defer to [authentication-security-standard.md](authentication-security-standard.md);
  apply the general security requirements here for everything else.
- Report which standards you reviewed and which gates you verified.

---

## 1. Release Gates

A change is production-ready only when all of these hold (mirrored by the planned CI in
[`../../.github/workflows/README.md`](../../.github/workflows/README.md)):

1. **Lint + type-check** clean for every touched package/app.
2. **Build** succeeds for every touched package/app.
3. **Tests pass** at the appropriate levels, and **coverage is preserved or improved** — see
   [testing.md](testing.md). No silent coverage regression.
4. **Failure paths are handled and tested** — see [error-handling.md](error-handling.md).
5. **No sensitive data is logged or returned** — see [observability.md](observability.md) and
   [error-handling.md](error-handling.md).
6. **Security checks pass** — see [Section 2](#2-general-security-requirements).
7. **Docs that move with the change are updated** — per the pre-commit workflow in `AGENTS.md`.

Until CI is implemented, reviewers verify these gates manually. As gates are automated, update the
CI README to record which are enforced by machine.

## 2. General Security Requirements

These apply to all code; authentication, sessions, tokens, cookies, and authorization are governed
in detail by [authentication-security-standard.md](authentication-security-standard.md) — follow it for
those concerns and the requirements below for the rest.

- **Validate and sanitize all input** at the boundary — see [error-handling.md](error-handling.md).
- **No secrets in source or logs.** Use environment variables/secret storage; never commit
  credentials, keys, or tokens. Secret scanning is a planned CI gate (`security.yml`).
- **Least privilege** for service-to-service and data access.
- **Dependency hygiene.** Keep dependencies current; no known high-severity vulnerabilities at
  release. Dependency scanning is a planned CI gate (`security.yml`).
- **Safe error surfaces.** No stack traces, internal detail, or enumeration in responses
  ([error-handling.md](error-handling.md)).
- **Protect sensitive data at rest and in transit**; honor the dataset rule in
  `.agents/rules/sensitive-local-datasets.md`.

## 3. Operational Readiness

- A deployable surface needs a documented deployment procedure — see [`../runbooks/`](../runbooks/).
  The public website has one ([`../runbooks/frontend-vercel-deployment.md`](../runbooks/frontend-vercel-deployment.md));
  backend services do not yet (a tracked gap).
- Services should expose health/liveness signals and not log sensitive data
  ([observability.md](observability.md)).
- Rollback and incident response are current gaps tracked in [`../runbooks/README.md`](../runbooks/README.md);
  a change that adds a new deployable surface should not be considered fully production-ready until
  its operational procedure exists.

## 4. Current State & Gaps

Verified today: tests run per-package locally; logging excludes sensitive data (tested in the
identity service). Not yet in place (do not claim these as met): automated CI/coverage gates,
dependency/secret scanning, backend deployment, rollback, health checks, monitoring, and incident
response. These are tracked in [`../../.github/workflows/README.md`](../../.github/workflows/README.md)
and [`../runbooks/README.md`](../runbooks/README.md).

---

## Related Standards

- [testing.md](testing.md) · [error-handling.md](error-handling.md) · [observability.md](observability.md)
- [authentication-security-standard.md](authentication-security-standard.md) — auth-specific security.
- CI: [`../../.github/workflows/README.md`](../../.github/workflows/README.md) · Ops: [`../runbooks/`](../runbooks/)
