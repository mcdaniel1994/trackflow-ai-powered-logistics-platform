# `.agents/rules/`

Scoped development rules for coding agents working in this repo. Apply any rule whose scope matches the files being touched.

Rules are the short, stable routing layer: they identify when deeper guidance applies and point to
the authoritative standard without duplicating it. See the canonical
[Rules and Standards Philosophy](../../AGENTS.md#rules-and-standards-philosophy).

## Catalog

| Rule | Scope | Summary |
|---|---|---|
| `preserve-delivered-engagements.md` | Always active | Do not rewrite delivered stakeholder briefs or delivered app behavior without confirmation. Covers `docs/briefs/`, `docs/archive/`, `docs/standards/visibility.md`, and `packages/shared/`. Retired code is preserved via `docs/archive/` retirement notes, not on-disk copies. |
| `authentication-security.md` | File-pattern: auth, sessions, tokens, cookies, protected routes, roles, permissions, AI-agent user context | Read `docs/standards/authentication-security-standard.md` before the change. |
| `database-engineering.md` | File-pattern and task based: database selection/configuration, repositories, persistence models, queries, schemas, migrations, seeds, recovery, and database operations | Read `docs/standards/database-engineering-standard.md`; preserve existing persistence decisions and approval-gate only high-risk production or non-disposable shared-data execution. |
| `public-ui-visibility.md` | File-pattern: `uis/website/**`, any folder with public-facing pages | Read `docs/standards/visibility.md` sections 1-6 before the change. Verify one H1, `<html lang>`, canonical, OG, Twitter Card, and parseable JSON-LD. |
| `sensitive-local-datasets.md` | File-pattern: `scripts/incidents-trackflow.csv`, future documented sensitive local datasets | Do not read, print, copy, summarize, export, or inspect sensitive local datasets unless the user explicitly authorizes that exact access. Prefer safe fixtures and aggregate-only outputs. |
| `testing-error-handling-ci.md` | File-pattern: production code, APIs/validation/persistence/failure paths, logging/monitoring, CI/coverage/build/deploy under `services/`, `packages/`, `uis/`, `.github/workflows/`, `docs/runbooks/` | Read the applicable `docs/standards/` doc (testing, error-handling, observability, production-readiness) before the change. Cover success and failure paths, add/update tests, preserve coverage, never log sensitive data, and report which standards were reviewed. |

## Adding a new rule

Each rule file must declare:

- **Rule Name**
- **Scope** (always active, or file-pattern based)
- **Required Behavior**
- **Examples** and **Non-Examples** when scope is file-pattern based

After adding a rule, list it in the catalog above with a one-line summary so agents can decide whether to load it.
