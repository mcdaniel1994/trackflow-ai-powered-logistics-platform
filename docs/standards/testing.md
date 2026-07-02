# Testing Standards

**Last reviewed:** June 2026  
**Next review due:** September 2026 (quarterly)

This file is the authority on how TrackFlow code is tested — what kinds of tests to write, what
coverage is expected, and the workflow for running tests locally. It applies across every service,
package, and app in the repository.

AI coding agents and human contributors must reference this file before adding or changing
behavior. When behavior changes, tests change with it.

---

## Scope

Applies to all production code: Python services under `services/`, shared libraries under
`packages/`, and the Next.js apps under `uis/`. It governs the *policy* (what and why). Concrete
enforcement values (exact thresholds, runner flags) live in test configuration and, later, in CI —
see [Coverage policy](#3-coverage-policy) and `../../.github/workflows/README.md`.

It does not restate auth or visibility test requirements — those remain in
[authentication-security-standard.md](authentication-security-standard.md) and [visibility.md](visibility.md).

---

## How AI Coding Agents Should Use This File

- Read this file before planning or implementing a change that adds or alters behavior.
- Add or update tests in the same change as the behavior — never defer them.
- Cover both the success path and the failure paths (see [error-handling.md](error-handling.md)).
- Preserve or improve existing coverage; do not remove tests to make a change pass.
- Report which standards you reviewed and what tests you added or changed.

---

## 1. Test Levels

Write the cheapest test that meaningfully exercises the behavior; add higher levels when the risk
warrants it.

- **Unit** — pure logic, validation, mappers, single functions/classes in isolation. Fast, no I/O.
- **Integration** — a route or service method against its real collaborators (repository, storage,
  validation). The default level for API endpoints. TrackFlow services already test at this level
  (e.g. `services/identity/tests/test_auth.py`, `services/supplier-directory/tests/test_api.py`).
- **End-to-end (e2e)** — a user-visible flow through a running app. Used for the back office today
  via Playwright (`uis/backoffice/tests/e2e/`). Reserve e2e for critical journeys; do not duplicate
  logic already covered by unit/integration tests.

## 2. What Must Be Tested

- Every new or changed public function, route, or component behavior.
- Every failure path the code deliberately handles: validation rejection, not-found, auth failure,
  duplicate, external/database failure, timeout.
- Security-sensitive behavior: that secrets/tokens are **not** logged or returned (the identity
  service asserts this with `caplog` in `services/identity/tests/test_password_reset.py` and
  `test_users.py` — follow that precedent).
- Regression: when fixing a bug, first add a test that fails for that bug.

## 3. Coverage Policy

- **Default expectation:** meaningful coverage of new and changed code — branches and error paths,
  not just the happy line. Coverage is a floor, not a goal; a green number with untested failure
  paths is not "done."
- **Ratcheting:** coverage should not regress. A change that lowers overall or per-package coverage
  needs a stated reason in the PR. Raise the floor opportunistically; never lower it silently.
- **Where the numbers live:** exact percentage thresholds and gating belong in test configuration
  and the future CI workflow (`../../.github/workflows/README.md`), not hard-coded in this prose, so
  policy and enforcement evolve independently. As of this writing no automated coverage gate is
  wired; until it is, reviewers enforce this policy manually.

## 4. Running Tests Locally

Python services (each is an isolated `uv` project; `testpaths = ["tests"]` per `pyproject.toml`):

```
uv run --project services/identity --extra dev pytest
uv run --project services/incident-processor --extra dev pytest
uv run --project services/supplier-directory --extra dev pytest
```

Back office (Next.js):

```
npm run test       --workspace uis/backoffice   # Vitest unit/component
npm run test:e2e   --workspace uis/backoffice   # Playwright e2e
```

Run `type-check`, `build`, and `lint` for every touched package or app as well — this is already
required by the pre-commit workflow in `AGENTS.md`.

## 5. Test Quality

- Tests assert behavior and contracts, not implementation details.
- Each test fails for exactly one reason; name it after the behavior under test.
- Use fixtures and factories over copy-pasted setup (see `conftest.py` patterns in each service).
- Never test against real secrets, production data, or the sensitive datasets named in
  `.agents/rules/sensitive-local-datasets.md` — use safe fixtures and aggregate-only outputs.

---

## Related Standards

- [error-handling.md](error-handling.md) — the failure paths that tests must cover.
- [observability.md](observability.md) — assertions that sensitive data is not logged.
- [production-readiness.md](production-readiness.md) — how tests and coverage become release gates.
