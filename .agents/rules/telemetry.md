# Telemetry

## Rule Name

Telemetry

## Scope

File-pattern and task based.

## Applies When

Planning, reviewing, or changing telemetry design or instrumentation: structured events, logs,
metrics, traces, correlation IDs, audit or security events, product analytics, telemetry retention,
or AI telemetry.

## Required Behavior

- Before planning or implementing, read
  [`docs/standards/telemetry-standard.md`](../../docs/standards/telemetry-standard.md).
- Treat that standard as the source of truth for telemetry purpose, safe event structure,
  minimization, retention decisions, and telemetry testing.
- Apply the runtime observability, authentication/security, database, testing, error-handling, and
  production-readiness standards whenever their scopes also match.
- Do not claim centralized telemetry, metrics, tracing, alerting, or analytics capabilities that are
  not implemented in the repository.

## Examples

- Adding a structured audit event to a FastAPI service.
- Introducing request correlation IDs, metrics, tracing, product analytics, or AI instrumentation.
- Reviewing whether telemetry fields, labels, retention, or access are safe.

## Non-Examples

- A copy-only documentation edit that merely mentions telemetry.
- A routine runtime log-level change governed only by `docs/standards/observability.md`.
