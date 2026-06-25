# Observability Standards

**Last reviewed:** June 2026  
**Next review due:** September 2026 (quarterly)

This file is the authority on logging, audit events, and monitoring across TrackFlow. The aim is to
make services debuggable in production without ever leaking sensitive data.

---

## Scope

Applies to all runtime code that logs, emits events, or exposes operational signals — Python
services under `services/` and the Next.js apps under `uis/`. It complements
[error-handling.md](error-handling.md) (what to do when something fails) by defining what to record.

---

## How AI Coding Agents Should Use This File

- Read this file before adding logging, audit events, or monitoring to any change.
- Never log secrets, tokens, passwords, reset links, or full PII — assert this in tests.
- Prefer one structured log line with context over scattered prints.
- Report which standards you reviewed.

---

## 1. Logging

- **Use the logging framework, not `print`/`console.log` for runtime diagnostics.** Python services
  use the standard `logging` module with a module-level logger (see
  `services/identity/identity/service.py`). Follow that pattern.
- **Log levels mean something:** `DEBUG` developer detail, `INFO` notable lifecycle events, `WARNING`
  recoverable/degraded conditions, `ERROR` handled failures needing attention, `CRITICAL` service
  cannot continue. Do not log routine success at `ERROR` or real failures at `INFO`.
- **Include context, exclude payloads.** Log the operation, the outcome, and identifiers needed to
  trace it — not request bodies, credentials, or full records.
- **Structured where it helps.** Favor key/value or structured fields over interpolated prose so
  logs are queryable when centralized logging is introduced (see [Gaps](#4-current-state--gaps)).

## 2. What Must Never Be Logged

Passwords and password hashes, tokens (session, reset, API), reset links/URLs, full PII, secrets and
connection strings, and the contents of sensitive datasets named in
`.agents/rules/sensitive-local-datasets.md`.

This is already enforced by tests in the identity service — `test_password_reset.py` and
`test_users.py` assert via `caplog` that tokens, reset links, and emails do not appear in logs. New
logging must be covered the same way (see [testing.md](testing.md)).

## 3. Audit Events & Monitoring

- **Audit security-relevant actions:** login success/failure, password reset request and completion,
  role/permission changes, and access to protected resources — recording *who/what/when/outcome*,
  never the secret material involved.
- **Make failures visible.** Handled errors (per [error-handling.md](error-handling.md)) should be
  logged at `WARNING`/`ERROR` with enough context to diagnose, and should be the signals a future
  monitor/alert watches.
- **Health signals.** Services should expose a basic liveness/health indicator so deployment and
  monitoring can verify them (tracked as a gap below and in
  `../runbooks/README.md`).

## 4. Current State & Gaps

Verified today: Python services use the standard `logging` module; sensitive-data exclusion is
tested. Not yet in place (intentional gaps, not requirements met):

- No centralized/structured log aggregation or retention.
- No metrics, tracing, or request-correlation IDs.
- No alerting or uptime monitoring.
- No standardized health-check endpoints across services.

These are tracked for the future CI/observability and operations work in
`../../.github/workflows/README.md` and `../runbooks/README.md`. Until they exist, this standard
governs *code-level* logging discipline; do not claim platform observability that is not wired.

---

## Related Standards

- [error-handling.md](error-handling.md) — what to log when a failure is handled.
- [testing.md](testing.md) — asserting sensitive data is not logged.
- [authentication-security-rule.md](authentication-security-rule.md) — auth audit and logging rules.
- [production-readiness.md](production-readiness.md) — observability as a release gate.
