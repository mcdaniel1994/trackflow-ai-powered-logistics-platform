# Telemetry Standard

**Last reviewed:** July 2026
**Next review due:** October 2026 (quarterly)

## 1. Scope And Authority

This standard governs how a project designs, structures, protects, reviews, and tests telemetry:
application logs, metrics, traces, audit and security events, product analytics, and AI telemetry.

It is a governance standard, not a logging-framework guide. The project's runtime observability,
security, data-retention, error-handling, testing, and release standards remain authoritative for
their respective concerns. Where they overlap, use this file to decide what may be collected and
how it is structured; use the runtime logging standard to decide how a signal is emitted.

## How AI Coding Agents Should Use This File

- Read this file before designing or changing telemetry, then load the related project standards.
- Treat the event contract and data-minimization rules as the default; apply tenant, consent, AI,
  and regulated-data safeguards only when the project context calls for them.
- Do not overstate observability capabilities. Record only what the repository actually emits and
  stores today.

## 2. Core Principles

- Collect telemetry only to answer a named operational, security, product, or quality question.
- Minimize at the source. Prefer opaque internal identifiers to personal or sensitive values.
- Treat every field as durable and broadly accessible. A downstream redaction pipeline is useful,
  but never the only safeguard.
- Keep telemetry out of the business critical path. A failed sink, serializer, or exporter must not
  fail, block, or materially slow the user operation.
- Keep environments separate. Local, CI, and test signals must not enter production telemetry
  stores, and production data must be identifiable and isolable.
- Use the smallest signal that answers the question. Telemetry is not a replacement for a database,
  queue, cache, or application record.

Never emit credentials, tokens, cookies, reset links, secrets, connection strings, private keys,
payment data, full personal data, raw request or response bodies, full records, or unreviewed
user-generated content. Apply the project's stricter security and data-handling rules whenever
they exist.

## 3. Signal Categories

Choose the signal for its purpose rather than forcing all information into logs.

- **Application logs:** diagnostic lifecycle and failure records.
- **Metrics:** numeric aggregates such as counts, rates, and durations. Labels must be bounded and
  must not contain PII, request IDs, user IDs, or other unbounded identifiers.
- **Traces:** causal spans for a logical operation across components. Trace attributes follow the
  same data-minimization rules as logs.
- **Audit and security events:** durable records of security- or compliance-relevant actions.
- **Product analytics:** behavioral information about a product surface. Collect only when there is
  a clear purpose and an appropriate privacy basis for the project's audience and jurisdiction.
- **AI telemetry:** safe operational metadata for model, retrieval, tool, and evaluation behavior.

## 4. Event Contract

Use stable, lowercase, dot-namespaced event names, such as `billing.invoice.paid` or
`auth.login.failed`. Names describe an outcome and never embed values or identifiers.

Every structured event should include the following when the signal and transport support it:

| Field | Requirement |
|---|---|
| `event` | Stable namespaced event name |
| `timestamp` | UTC RFC 3339 timestamp |
| `service` | Emitting component or service |
| `env` | Runtime environment |
| `severity` | Applicable log or security-event severity |
| `correlation_id` | Request or trace identifier, when available |
| `outcome` | Safe result such as `success`, `failure`, or `denied`, when applicable |

Use safe, purpose-specific context only: opaque actor or entity IDs, a duration, a bounded reason
code, or a low-cardinality dimension. For projects with tenants, include a tenant identifier on
events concerning tenant data and enforce tenant scoping in telemetry queries and exports.

Document the purpose, allowed fields, and retention decision for each new event type or event
family. Treat a material event-schema change as a privacy and compatibility review point.

## 5. Data Protection And Retention

- Redact, drop, or transform PII-prone values before they reach a telemetry call. Free text,
  search terms, incident notes, prompts, and tool arguments require explicit review.
- A keyed hash is **pseudonymous**, not anonymous: it can still be linkable and may be reidentified
  by someone with access to the key or source data. Protect it accordingly.
- Define retention before collection. Choose it by signal purpose, risk, legal or contractual
  obligations, storage cost, and incident-investigation needs; document any required exception.
- Typical starting points are short retention for debug logs and traces, longer retention for
  aggregated metrics, and risk-based retention for audit and security records. Do not assume one
  universal duration is compliant for every project.
- Restrict access to audit, security, and sensitive debugging telemetry. Never return raw telemetry
  in API error responses or expose it directly to end users.

## 6. Implementation Guardrails

- Put shared field assembly, redaction, correlation lookup, and transport handling behind a small
  service or application helper. Do not require a new abstraction for a single ordinary log line,
  but do not scatter complex event construction through business handlers.
- Use field allowlists for event families that accept arbitrary or PII-prone context. Reject or drop
  unexpected fields before export.
- Sample high-volume diagnostics only when the sampling decision is recorded or otherwise visible
  to consumers. Do not sample audit or security events unless an approved risk decision says so.
- Do not perform a synchronous network round trip solely to emit telemetry on a request path.
- Propagate a correlation ID from the boundary when the architecture supports it. It is a join key,
  not a substitute for authorization or tenant isolation.

## 7. Audit And Security Telemetry

Record who, what, when, and outcome for security-relevant actions without recording the protected
material involved. Typical coverage includes authentication outcomes, authorization denials,
role or permission changes, privileged actions, sensitive-data export or import, configuration or
deployment changes, and suspected abuse.

Audit and security events should be structured, access-restricted, append-only in intent, and
reviewable. Their exact retention, immutability, and review cadence depend on the project's risk,
contractual obligations, and applicable law.

## 8. AI Telemetry

For applications with AI features, capture safe metadata by default: provider and model version,
token usage, latency, finish reason, tool name and outcome, retrieval IDs or counts, and safe
evaluation results. Keep raw prompts, completions, retrieved text, and tool arguments out of normal
telemetry.

Content capture is an explicit, time-bounded debugging or evaluation decision. It requires
redaction, restricted access, a defined retention period, and approval appropriate to the data
sensitivity. Treat model and tool output as untrusted before it enters telemetry or agent context.

OpenTelemetry GenAI semantic conventions are useful interoperability guidance, but evolve over
time. Adopt their fields deliberately rather than treating any pre-release convention as a fixed
application contract.

## 9. Verification Checklist

Before adding or changing telemetry, confirm:

- It answers a named question and uses the right signal category.
- Its fields are minimized, safe, and documented; forbidden values cannot reach the sink.
- Metric labels are bounded and contain no personal or unbounded identifiers.
- Tenant, consent, regulated-data, and AI safeguards apply where the project uses those concepts.
- It cannot break the business path and cannot route non-production data to a production sink.
- Retention, access, sampling, and correlation decisions are appropriate for the signal.
- Tests assert both expected emission and absence of representative forbidden data.

## 10. TrackFlow Implementation Notes

This appendix applies the portable core to this repository. It is not part of the reusable standard.

- [observability.md](observability.md) owns TrackFlow runtime logging, the canonical never-log list,
  audit baseline, and current observability gaps. This file governs telemetry collection and shape.
- Related local authorities are [authentication-security-standard.md](authentication-security-standard.md)
  for auth and agent-context safety, [database-engineering-standard.md](database-engineering-standard.md)
  for stored telemetry lifecycle, [testing.md](testing.md) for telemetry assertions,
  [error-handling.md](error-handling.md) for safe failure content, and
  [production-readiness.md](production-readiness.md) for release gates.
- Current baseline: Python services use standard logging with structured key/value-style context;
  identity-service tests assert that sensitive data is absent from logs (including the Engagement 6
  `auth.login.*` / `auth.session.expired` audit lines); Identity, Central API, and Back Office expose
  health checks.
- Engagement 6 Phase 1 (implemented in code, verified locally; production collection gated on a
  scheduled retention prune before `TELEMETRY_ENABLED=true`): Central API owns a single
  `telemetry_events` table holding only best-effort diagnostics (`inventory.dispatch.rejected`,
  `api.access.denied`) emitted after the response via a background task, with allowlisted PII-free
  fields, `operational`/`security` category retention, and a `prune_telemetry_events` command. Exact
  warehouse metrics (dispatch/receiving/loss) are read directly from `StockEntry`/`StockExit`. The
  Back Office `/backoffice/telemetry` route exposes bounded, aggregates-only reporting. The living
  per-signal reference is [`../runbooks/telemetry-inventory.md`](../runbooks/telemetry-inventory.md).
- Not yet implemented: metrics, distributed tracing, platform-wide correlation IDs, alerting or
  uptime monitoring, a browser product-analytics/ingest pipeline, a durable telemetry event queue,
  and production product AI agents. This standard therefore governs design and code-level discipline;
  it does not claim those platform capabilities exist.
- The relevant repository areas are `services/`, `uis/`, `packages/`, and future product-agent work
  under `agents/`, `skills/`, and `data/`. TrackFlow tenant-specific telemetry must use opaque
  internal identifiers and support tenant-scoped access.

## Sources To Consult

- [OpenTelemetry documentation](https://opentelemetry.io/docs/) -- logs, metrics, traces, and core
  semantic conventions.
- [OpenTelemetry GenAI semantic conventions](https://github.com/open-telemetry/semantic-conventions-genai)
  -- evolving conventions for GenAI spans, metrics, and events.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
  -- safe logging and exclusion practices.
- [NIST SP 800-92](https://csrc.nist.gov/pubs/sp/800/92/final) -- log-management planning.
- [NIST Privacy Framework](https://www.nist.gov/privacy-framework) -- privacy-risk management.
- [GDPR Article 5](https://gdpr-info.eu/art-5-gdpr/) -- purpose limitation, data minimization, and
  storage limitation where applicable.
