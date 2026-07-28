# Engagement 6.1 Local Review Evidence — 2026-07-28

## Status

Phase 6.1 is implemented, locally verified, and deployed as immutable image `13bba2e` through
Alembic `20260728_0011`. On 2026-07-28 the owner directed the team to skip the remaining controlled
production exercises and proceed. Phase 6.1 is closed by that explicit exception; the omitted
evidence is not represented as passing. Phase 6.2 has started; Phases 6.3–6.4 have not.

The mandatory read-only production rescan was completed before code changes. Its redacted evidence
is in [`engagement-6.1-production-rescan-2026-07-28.md`](engagement-6.1-production-rescan-2026-07-28.md).
The measured volume and query times did not cross a stop threshold.

## Implemented

- Additive Alembic revision `20260728_0011` creates sanitized, exact-once
  `reporting.pipeline_run_attempts` history with the required uniqueness, ordering index, and
  cascade ownership.
- Retry exhaustion remains `MAX_ATTEMPTS_EXCEEDED` on the parent run while each attempt preserves
  its originating safe error code, stage, exception class, timing, outcome, and provenance.
- Reporting status returns bounded attempt history, including `run_id`, without exposing exception
  messages, SQL, payloads, connection details, client names, or secrets.
- Back Office liveness, core readiness, and reporting verification are separate signals. Only core
  readiness participates in automatic release rollback; reporting verification is uploaded as
  bounded evidence.
- Lease, stale-run, watchdog, heartbeat, and renewal ordering follows the specification. The
  maintenance worker can enqueue and observe a checkpoint but cannot claim, execute, or publish it.
- The size guard pauses at the soft limit, refuses every unattended destructive reset, consumes an
  exact one-shot owner approval before checkpoint work, and still blocks reset unless the normal
  worker completes that checkpoint successfully. The normal feed interval is 15 seconds.
- Optional host-persisted reporting logs use bounded rotation and daily age/byte pruning. Stdout
  remains active when no path is configured.

## Local verification

| Gate | Result |
|---|---|
| Central API pytest + branch coverage | 173 passed; 93% |
| Central API Ruff | Passed |
| Central API strict mypy | Passed, 49 source files |
| Data-pipeline pytest + branch coverage | 118 passed; 90.58% |
| Data Ruff / strict mypy / build | Passed |
| Release workflow contract tests | 10 passed |
| Back Office type-check / lint / tests / build | Passed; 122 tests |
| Migration head on disposable PostgreSQL | `20260728_0011` |
| Docker Central API build | Passed |
| Whitespace audit | `git diff --check` passed |

The disposable database and Docker checks used only repository-defined local credentials. No
production credential or connection string was recorded.

## Open acceptance actions and deliberate stop

The following specification §4.1.i items require an approved production/Coolify exercise and were
not inferred from local tests:

1. Stop the production reporting worker for at least 15 minutes and record Back Office routing,
   unrelated 5xx/404s, and rollback behavior.
2. Break each core dependency deliberately and prove the release gate rolls back.
3. Remove a reporting grant and prove only reporting verification fails.
4. Inject a failure at every stage, replace the container, and retrieve the durable attempt record.
5. Verify the owner-approved `reporting-logs` volume at `/var/log/trackflow/reporting`, ownership
   and modes, 10 MiB/nine-backup rotation, 14-day retention, 250 MiB ceiling, Coolify notification
   destination, and preserved exit events.
6. Record Traefik routing and Coolify behavior for an unhealthy container and verify whether the
   deployed production image contains commit `fe430ab`.

The owner approved the recommended persisted-log configuration and continuation on 2026-07-28.
Production rollout remains blocked until a configured Coolify notification destination is verified.
No production mutation was attempted while preparing this review.

## Review decision

**Approved to continue, production gate still open.** This authorizes scoped publication and the
controlled Phase 6.1 production acceptance exercises. It is not a passing Phase 6.1 review gate:
do not begin Phase 6.2 until all production evidence above passes and the owner accepts the
completed gate.
