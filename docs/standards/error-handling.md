# Error Handling Standards

**Last reviewed:** June 2026  
**Next review due:** September 2026 (quarterly)

This file is the authority on how TrackFlow code handles failure — input validation, error
responses, and failures from databases and external services. It applies across every service,
package, and app.

The goal: fail predictably, never leak sensitive detail, and give callers an actionable, safe
response.

---

## Scope

Applies to all code that validates input, talks to storage, calls another service, or returns
errors to a caller or UI. Auth-specific error behavior (login failure messaging, token handling,
lockout) remains governed by [authentication-security-standard.md](authentication-security-standard.md);
this file references it rather than restating it.

---

## How AI Coding Agents Should Use This File

- Read this file before adding or changing an API, a validation path, a persistence call, or any
  failure path.
- For every new behavior, handle and test the failure paths, not only the success path
  (see [testing.md](testing.md)).
- Never expose internal detail (stack traces, queries, secrets, raw exceptions) in a response or
  client-visible error.
- Report which standards you reviewed.

---

## 1. Error-Handling Patterns

- **Use typed domain exceptions**, then translate them at the boundary. TrackFlow's identity service
  already does this: domain errors like `AuthenticationError` and `NotFoundError` (service layer) and
  `DuplicateEmailError` (repository layer) are raised internally and mapped to HTTP responses at the
  route layer. Follow that shape.
- **Catch narrowly.** Catch the specific exception you can handle; let unexpected errors propagate
  to a single boundary handler that returns a safe generic response and logs the detail server-side.
- **No silent failures.** Never swallow an exception without either handling it meaningfully or
  logging it (see [observability.md](observability.md)). An empty `except`/`catch` is a defect.
- **Fail closed on security decisions.** When authorization or validation is uncertain, deny.

## 2. API Input Validation

- Validate at the boundary before doing work. Python services use Pydantic models on FastAPI
  routes; UIs validate before calling the BFF.
- Reject invalid input with a clear, field-level message and the correct status code (`422`/`400`).
  Do not partially process invalid requests.
- Treat all client input as untrusted, including headers and IDs from authenticated callers.

## 3. Safe Error Responses

- **Map errors to correct status codes:** `400/422` invalid input, `401` unauthenticated, `403`
  unauthorized, `404` not found, `409` conflict/duplicate, `500` unexpected. `5xx` is for *our*
  faults, not the caller's.
- **Generic outward, detailed inward.** Return a stable, non-revealing message to the caller; log
  the full detail server-side with enough context to debug.
- **No sensitive data in responses or error bodies:** no secrets, tokens, password material, full
  PII, internal paths, queries, or stack traces.
- **Do not enable enumeration.** Follow the auth standard's pattern — e.g. identical responses for
  "unknown email" and "wrong password," and for password-reset requests regardless of account
  existence. See [authentication-security-standard.md](authentication-security-standard.md).

## 4. Database & Storage Failures

- Assume storage can fail or be unavailable. Wrap storage calls so a failure becomes a typed error,
  not a leaked driver exception.
- Keep writes consistent: validate first, then write; avoid partial multi-step writes without a
  recovery path. TrackFlow services use TinyDB today — the same discipline applies and must carry
  forward to any future SQL/managed store.
- Surface storage failures as `503`/`500` with a safe message; log the cause server-side.

## 5. External-Service Failures

- **Set timeouts** on every outbound call. A missing timeout is a defect.
- **Decide the failure mode explicitly:** retry (with backoff, only for idempotent calls), fall back
  to a safe default, or fail fast — and document which, in code.
- **Isolate the blast radius.** A dependency being down should degrade one feature, not crash the
  service. Do not let an external failure surface as an unhandled `500` with internal detail.
- Log the dependency, the operation, and the outcome (not the payload) for diagnosis.

---

## Required Tests

For each handled failure path, add a test that asserts the status code, the safe (non-leaking)
message, and that no sensitive data appears in the response or logs. See [testing.md](testing.md)
section 2.

## Related Standards

- [testing.md](testing.md) — coverage of failure paths.
- [observability.md](observability.md) — what to log when an error is handled.
- [authentication-security-standard.md](authentication-security-standard.md) — auth-specific error behavior
  and anti-enumeration responses.
- [production-readiness.md](production-readiness.md) — error handling as a release gate.
