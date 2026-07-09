# `docs/standards/`

Cross-cutting standards that apply across engagements.

Standards live here when they govern how multiple apps, packages, or pipelines must behave — not engagement-specific scope (which lives in `docs/briefs/`).

Standards are the evolving, authoritative engineering requirements loaded through matching rules.
See the canonical [Rules and Standards Philosophy](../../AGENTS.md#rules-and-standards-philosophy).

## Index

| Standard | Scope |
|---|---|
| [authentication-security-standard.md](authentication-security-standard.md) | Auth, sessions, tokens, cookies, authorization, protected routes, and AI-agent user context |
| [database-engineering-standard.md](database-engineering-standard.md) | Database and persistent-storage design, queries, integrity, migrations, concurrency, recovery, and high-risk production operations |
| [visibility.md](visibility.md) | Public-facing pages: semantic HTML, WCAG 2.1 AA, SEO, GEO, Schema.org, Core Web Vitals, bot access |
| [testing.md](testing.md) | Test levels, what to test, coverage policy and ratcheting, local test workflow |
| [error-handling.md](error-handling.md) | Error patterns, API input validation, safe error responses, database and external-service failures |
| [observability.md](observability.md) | Logging, audit events, monitoring, and what must never be logged |
| [telemetry-standard.md](telemetry-standard.md) | Telemetry purpose, event structure, privacy governance, retention, analytics, and AI telemetry |
| [production-readiness.md](production-readiness.md) | Release/quality gates and general (non-auth) security requirements |

The testing, error-handling, observability, and production-readiness standards form the engineering
quality framework. Agents are routed to them by [`.agents/rules/testing-error-handling-ci.md`](../../.agents/rules/testing-error-handling-ci.md).
Related operational and CI material lives in [`../runbooks/`](../runbooks/) and
[`../../.github/workflows/README.md`](../../.github/workflows/README.md).
Telemetry-design work is routed by [`.agents/rules/telemetry.md`](../../.agents/rules/telemetry.md).

## Conventions

- One topic per file.
- Each standard names its scope and review cadence at the top.
- Reference standards from component READMEs (e.g., `uis/website/README.md` → `visibility.md`) so contributors find them at the point of work.
- Standards link to supporting implementation files, runbooks, and CI docs; they must not duplicate
  normative content that another standard owns — link to it instead.

## Exceptions

Standards are the default, not an absolute. To deviate:

1. State the specific standard requirement, why compliance is infeasible or counter-productive for
   this change, and the scope of the exception.
2. Propose the safest compliant alternative considered and why it was not taken.
3. Get explicit approval from the repository owner before merging.
4. Record the exception and its rationale in the change's PR/description (and in the engagement brief
   if it is ongoing). Auth and visibility standards have their own override paths — follow those when
   the deviation concerns them.

Silent non-compliance is not an exception — it is a defect.
