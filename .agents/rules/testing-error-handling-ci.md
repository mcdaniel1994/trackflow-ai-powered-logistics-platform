# Testing, Error Handling & CI

## Rule Name

Testing, Error Handling & CI

## Scope

File-pattern based.

## Applies When

Any change to production code, APIs, validation, persistence or failure paths, logging/monitoring,
or CI/coverage/build/deploy/release configuration — i.e. anything under `services/`, `packages/`, or
`uis/` that adds or changes behavior, and any work on `.github/workflows/` or `docs/runbooks/`.

## Required Behavior

Before planning or implementing, read the applicable canonical standard(s) and treat them as the
source of truth — do not duplicate their content here:

- Production code changes → [`docs/standards/testing.md`](../../docs/standards/testing.md)
- APIs, validation, persistence, and failure paths → [`docs/standards/error-handling.md`](../../docs/standards/error-handling.md)
- Logging, audit events, service failures, and monitoring → [`docs/standards/observability.md`](../../docs/standards/observability.md)
- CI, coverage gates, builds, deployments, and release checks → [`docs/standards/production-readiness.md`](../../docs/standards/production-readiness.md)

Then:

- Consider both success and failure paths.
- Add or update tests in the same change as any behavior change.
- Preserve or improve coverage; never lower it silently.
- Never expose or log sensitive data (secrets, tokens, reset links, full PII).
- Report which standards you reviewed and which gates you verified.
- For planning-only work, follow the approval gates: present the plan and wait for approval before
  implementing.

## Examples

- Adding or changing a FastAPI route in `services/*`.
- Adding validation or a database/external-service call.
- Adding logging or an audit event.
- Editing `.github/workflows/` or a deployment runbook.

## Non-Examples

- Pure copy/markdown edits with no behavior change.
- Auth-specific work — use `.agents/rules/authentication-security.md` (defer auth security to
  `docs/standards/authentication-security-rule.md`).
- Public-page visibility work — use `.agents/rules/public-ui-visibility.md`.
