# TrackFlow — Combined Quality Evaluation & Remediation Plan

**Type:** Planning-only (evaluation + phased remediation). No code to be written until approved.
**Date:** 2026-06-24 · **Branch:** `main`
**Standards compared against:** `docs/standards/testing.md`, `error-handling.md`, `observability.md`,
`production-readiness.md`, `authentication-security-rule.md`; rule `.agents/rules/testing-error-handling-ci.md`;
CI design `.github/workflows/README.md`; ops `docs/runbooks/README.md`.

## Context

The repo recently gained a set of engineering-quality standards and a matching agent rule. This is a
fresh, evidence-based evaluation of the codebase against those standards — test coverage, test
quality, error handling, observability, and production-readiness — re-running the suites live rather
than trusting the prior audit. It ends with a prioritized, phased remediation plan and the decisions
that need sign-off. The intended outcome is a clear, approved backlog that makes changes meet the new
standards before a production push.

**Evidence legend:** `[V]` Verified (ran/read this session) · `[A]` Assumption · `[R]` Recommendation ·
`[?]` Could not verify.

**Approved scoping decisions (from this planning session):**
- Coverage approach = **risk-based ratchet**, enforced per package/app, changed-code coverage + no
  regression during transition; meaningful failure-path tests over number-chasing. Targets folded
  into the phases below.
- Auth-standard production deviations (TinyDB-as-source-of-truth, no rate limiting, no CSP/security
  headers) → **tracked here as P1/P2 with acceptance criteria; the SQL migration is a separate
  engagement.** Rate limiting + security headers are closed within this plan.

---

## 1. Tests & coverage discovered (by service / package / UI) `[V]`

All suites green this session: **100 tests pass** (78 Python + 22 frontend). Coverage measured with
ephemeral tools only (`pytest-cov` via `uv run --with`, `@vitest/coverage-v8` via `npm i --no-save`) —
nothing persisted.

| Area | Runner | Tests | Coverage (stmts) | Notes |
|---|---|---|---|---|
| `services/identity` | pytest (integration) | 22 | **90%** | weakest: `email.py` 69%, `cli.py` 80%, `service.py` 85%, `main.py` 88% |
| `services/incident-processor` | pytest | 36 | **96%** | weakest: `cli.py` 76% |
| `services/supplier-directory` | pytest | 20 | **91%** | weakest: `seed.py` 50% |
| `packages/trackflow_auth` | (none of its own) | 0 | **88%** | covered only transitively via identity tests — no dedicated suite |
| `uis/backoffice` | vitest | 22 | **20.5%** | branches 20.1%, funcs 19.4% |
| `uis/backoffice` e2e | playwright | 1 spec | not run | `tests/e2e/auth-smoke.spec.ts`; needs live services |
| `uis/website` | none | 0 | **0%** | no test runner/script at all |

**Back-office coverage detail** `[V]`: API routes — `users` 100%, `auth` 68%, **`incidents`/`suppliers`/`talent` 0%**.
`app/(protected)/layout.tsx` (auth gate) **0%**. `lib/server/proxy.ts` 85%, `request-context.ts` 0%.
`lib/auth` 34% (redirects 87%, client-http 79%, csrf 75%, **session 22%, errors 10%, api 0%, context 0%**).
`lib/suppliers`/`lib/talent`/`lib/incident-api`/`lib/scoring` all **0%**. Auth components 82%; admin 63%;
most other components 0%.

**Validation commands used** (per `testing.md` §4):
```
uv run --project services/identity --extra dev pytest
uv run --project services/incident-processor --extra dev pytest
uv run --project services/supplier-directory --extra dev pytest
npm run test --workspace uis/backoffice
# coverage (ephemeral): uv run --with pytest-cov pytest --cov=<pkg> --cov-report=term-missing
#                       npx vitest run --coverage (with @vitest/coverage-v8 installed --no-save)
```

## 2. Strong areas `[V]`

- **Auth core is genuinely production-grade**, not prototype: `trackflow_auth/verifier.py` pins
  `alg=RS256`, rejects `alg:none`/client-chosen alg, verifies signature + `iss` + `aud` + `exp` and
  required claims + `token_type`. `security.py` uses Argon2id at standard params (t=2, m=19456 KiB, p=1),
  hashes refresh **and** reset tokens at rest (sha256), constant-time password verify, short-lived
  access tokens + opaque rotating refresh tokens, CSRF double-submit with `hmac.compare_digest`.
- **Typed-domain-exception → HTTP-boundary mapping** in the identity and supplier services exactly
  matches `error-handling.md` §1 (e.g. `AuthenticationError`/`NotFoundError`/`DuplicateEmailError`
  → 401/404/409). Correct status-code discipline (400/401/403/404/409).
- **Anti-enumeration** honored: generic "Invalid email or password" (`main.py:114`) and uniform
  password-reset responses.
- **Sensitive-data-not-logged is tested** via `caplog` in `identity/tests/test_password_reset.py`
  and `test_users.py` — the precedent `observability.md` §2 asks for.
- **Deliberate PII redaction in the data model:** supplier list/detail responses redact raw
  `contact_email` via `SupplierPublic` (raw email only via the explicit `/contact` endpoint); incident
  CSV validation errors carry only row/field/code and tests assert customer emails never appear in
  API/export output. Matches `error-handling.md` §3. (Caveat: the 422 path bypasses this — see §5.)
- **CORS** is an explicit env-driven allowlist with `allow_credentials=True` against specific origins
  (never `*`) across all three services — matches auth standard §10/§12.
- **Health endpoints exist and are tested** (`/health` → `{"status":"ok"}`) in all three services.
- Python integration tests assert behavior/contracts at the right level (`testing.md` §1/§5).

## 3. Missing or weak coverage `[V]`

- **Back-office auth/BFF boundary is the lowest-covered, highest-risk surface:** the protected-route
  gate (`app/(protected)/layout.tsx`, 0%), `getServerSessionUser` (`lib/auth/session.ts`, 22%), and
  three BFF proxy routes (incidents/suppliers/talent, 0%). Only the `users` route is tested.
- **`trackflow_auth` has no dedicated test suite** — the shared verification gate for all three
  services is covered only incidentally. Its failure branches (expired/tampered/wrong-`aud`/wrong-`alg`/
  missing-claim) deserve direct tests (auth standard §17).
- **Client auth flow untested:** `lib/auth/api.ts` (0%), `context.tsx` (0%), `errors.ts` (10% — the
  FastAPI `detail[]`→field-error mapping branch that drives every form is uncovered).
- **Domain logic untested:** `lib/scoring.ts` (0%, pure logic — cheap/high value), supplier/talent API
  clients (0%).
- **`uis/website` has zero test infrastructure** (low-interactivity, retirement-flagged — lowest priority).
- Service gaps: identity `email.py` 69% (reset-email failure path), supplier `seed.py` 50%.

## 4. Strong error-handling patterns `[V]`

- Typed domain exceptions translated at the route boundary; narrow `except` of specific argon2
  exceptions in `verify_password`; `raise ... from exc` chaining preserved server-side.
- Email send wraps the provider call and re-raises a typed `EmailDeliveryError` with a generic
  message — no provider internals leak (`email.py:46-66`).
- Pydantic validation at FastAPI boundaries; supplier service rejects invalid country/category
  filters with 400 and field context.
- "Fail closed": empty public key → 401; missing claims → 401 (`verifier.py`).

## 5. Missing or weak error handling `[V]`

- **🔴 CRITICAL — default FastAPI 422 responses echo the rejected input (confirmed live leak).**
  Probed `POST /auth/reset-password` with a too-short password →
  `422 {"detail":[{"type":"string_too_short","loc":["body","new_password"],"input":"short",...}]}` `[V]`.
  Pydantic v2's per-field `input` reflects the **submitted value back in the response body** — for a
  reset/change-password form the most common validation failure echoes the user's plaintext password;
  the same shape would echo emails/PII/other field values, and any proxy or response-logging layer
  would then capture it. Direct violation of `error-handling.md` §3 and `observability.md` §2 / auth
  standard §13, and a `production-readiness.md` §1.5 release-gate failure. Fix: a custom
  `RequestValidationError` handler in every service that returns field name + safe message only
  (strip `input`/`ctx`), with tests asserting passwords/tokens/emails never appear in the body.
- **BFF proxy does not handle upstream connection failures (most likely production failure mode).**
  `lib/server/proxy.ts:126` does not wrap `fetch`. If any of the 3 backends is down (`ECONNREFUSED`/
  unreachable), `fetch` throws and the route returns Next's default **HTML 500**, which `parseAPIError`
  cannot parse — the user gets a confusing generic failure whenever one service is down (the expected
  partial-outage mode of a 4-service deployment). Fix: try/catch → JSON **503** `{detail: "Service
  temporarily unavailable"}`.
- **Missing outbound timeouts (systemic) — a defect per `error-handling.md` §5 ("a missing timeout is
  a defect"):**
  - Frontend: **every** `fetch` lacks a timeout/`AbortSignal` — `lib/server/proxy.ts:126` (BFF→service),
    `lib/auth/session.ts:18`, `lib/auth/client-http.ts:53/72/79`, `lib/talent/api.ts:197`,
    `lib/suppliers/api.ts:99`. A hung backend hangs the Next.js route. **Aggravated by an external
    third-party dependency:** the talent proxy targets `https://playground.4geeks.com/tracker/api/v1`
    (`lib/server/service-urls.ts:16`) `[V]` — an outside service that can hang indefinitely.
  - Python: `resend.Emails.send()` (`email.py:54`) has no timeout.
- **No Next.js error boundaries anywhere `[V]`** — no `error.tsx`, `global-error.tsx`, or
  `not-found.tsx` exist in either app. `getServerSessionUser` (`session.ts:18`) fetches identity during
  SSR of the protected layout and is **not** wrapped/fail-safe — if identity is down, the entire
  protected tree throws to Next's default error screen. Fix: `app/global-error.tsx`, a `(protected)`
  route-level `error.tsx`, `not-found.tsx`, and make `getServerSessionUser` fail safe (treat as
  logged-out / degraded banner).
- **No global/unexpected-error boundary handler** in any FastAPI app (no `add_exception_handler`):
  unexpected exceptions (TinyDB I/O, the `RuntimeError` from `sign_access_token` on a misconfigured
  RS256 key `security.py:97`, "service is not initialized" `main.py:86`) fall through to FastAPI
  defaults with no logging/correlation. `error-handling.md` §1 asks for a single boundary returning a
  safe generic 500 and logging detail server-side. `[V]` none present.
- **Supplier creation has no conflict/uniqueness handling `[V]`** — `POST /suppliers`
  (`main.py:67`→`service.py:56`) inserts directly; `find_by_identity` exists but is used only at seed
  time, so duplicate name+country rows are creatable with no **409** — inconsistent with identity's
  `DuplicateEmailError`→409 pattern (`error-handling.md` §3).
- **Supplier/incident repositories lack write serialization `[V]`** — identity uses an `RLock`
  (`repository.py:74`); the other two repos have none. TinyDB is not concurrency-safe, so concurrent
  writes risk corrupt/lost data surfacing as opaque 500s (`error-handling.md` §4).
- **No typed wrapping of storage failures** (`error-handling.md` §4): TinyDB calls can raise raw
  driver/OS exceptions that would surface as unhandled 500s rather than a safe 503/500. Related:
  `_is_expired` calls `datetime.fromisoformat` on persisted values unguarded (`service.py:362`) — a
  malformed stored timestamp raises an uncaught 500 instead of a controlled auth failure.
- **Client `parseAPIError` drops object-shaped `detail` `[V]`** — incident-processor returns
  `detail={"code","message"}` (`incident-processor/main.py:51` and the export 404), but the client
  parsers handle only string or `detail[]` array (`lib/talent/api.ts:139`), so the specific CSV error
  reason never reaches the user (degrades to "Request failed with status 400").
- **Frontend renders raw upstream `detail`/`message` strings.** `parseAPIError` displays upstream
  text directly — safe only while every upstream is disciplined; risky for the **external** talent API
  and future services, where a stack trace or secret-bearing message would render in the UI. `[R]`
  normalize display by status/code rather than echoing arbitrary upstream strings (`error-handling.md` §3).
- **Supplier `/contact` reveal is authenticated but not permission-scoped `[V]`** — any active non-temp
  Back Office user can reveal raw `contact_email` (`main.py:94`); production should gate it behind a
  named permission and emit an audit event (auth standard §11/§13, least privilege).
- **Domain services trust JWT claims without per-request user/session reload `[V]`** — supplier/incident
  authorize purely on access-token claims; a suspension/revocation only takes effect after token expiry
  (15 min). Acceptable under auth standard §7 **only** with short-lived tokens (which hold here), but it
  must be documented and is removed by the future central-auth/SQL introspection layer. `[A]` tie to the
  separate SQL engagement.
- **Incident upload has no size/content-type guard `[V]`** — `incident-processor/main.py` reads the whole
  uploaded file into memory before parsing; production needs an upload-size limit and content-type check
  with controlled errors *before* parsing (resource-exhaustion risk; `error-handling.md` §2).
- **`catch {}` blocks** in frontend (`talent/api.ts:116`, `auth/context.tsx:44`, `redirects.ts:16`,
  `errors.ts:8`, `suppliers/api.ts:25`, `incident-api.ts:11`) — `[A]` most look like intentional
  parse/no-op fallbacks, but each must be confirmed to not silently swallow a real failure
  (`error-handling.md` §1).
- **UI maps 422 → not-found `[A]`** — talent/supplier detail pages treat a 422 as "not found", which can
  hide malformed-ID or validation bugs; distinguish 404 from 422 once the validation envelope is safe.

## 6. Logging & observability gaps `[V]`

- **The entire backend has exactly 3 logging statements `[V]`** — a module logger plus **2** email
  -delivery warnings (`service.py:265,282`). `incident-processor` and `supplier-directory` have **no
  logging at all**. The frontend has **0** `console.error`/telemetry. A production incident would be
  nearly undebuggable. Violates `observability.md` §1/§3.
- **High-signal security events are silent `[V]`** — refresh-token **reuse → whole-family revoke**
  (`service.py:185-205`, a likely account-compromise signal) logs nothing; failed logins, authorization
  denials, admin mutations (status change, delete, session revoke), and all 5xx are unlogged
  (`observability.md` §3, auth standard §13). Login success/failure, reset request/completion, and role
  changes are not emitted/queryable.
- **No request-correlation IDs**, no structured logging, no central aggregation (acknowledged platform
  gaps in `observability.md` §4 — not claimed as met).
- **Discrepancy to flag:** `observability.md` §4 and `runbooks/README.md` list "no standardized
  health-check endpoints" as a gap, but `/health` endpoints **do exist and are tested** in all three
  services `[V]`. Recommend updating the docs to reflect this (still no monitoring wired).

## 7. Standards compliance summary

| Standard | Status | Evidence |
|---|---|---|
| `testing.md` | **Partial** — Python strong (88–96%), back-office weak (~20%), website none; no CI coverage gate (expected, `[V]`) | §1 |
| `error-handling.md` | **Fails on a core rule** — boundary mapping good, but **default 422 echoes submitted input (confirmed password leak)**, missing timeouts, no global 500 handler, no upstream-failure/storage-failure handling | §5 |
| `observability.md` | **Weak** — 3 log statements backend-wide; no audit/correlation; sensitive-data-exclusion tested only where logging exists | §6 |
| `production-readiness.md` | **Gate failing** — §1.5 "no sensitive data returned" is violated by the 422 leak; also no automated CI/coverage/secret/dependency gates (expected), no backend deploy/rollback | §1,9 |
| `authentication-security-rule.md` | **Strong core, prototype storage** — verification/hashing/CSRF compliant; deviations: TinyDB≠SQL, no rate limiting/lockout, no CSP/security headers, `cookie_secure` env-gated (must be true in prod) | §2,5 |

## 8. Prioritized risk list (P0–P3)

- **P0-0** `[V]` **Confirmed sensitive-data leak:** default FastAPI 422 echoes submitted input
  (plaintext password reproduced live). Release-gate violation; fix with a custom validation handler in
  all services + leak-assertion tests. **Highest priority.**
- **P0-1** `[V]` Back-office auth gate + `getServerSessionUser` untested (0%/22%) — no test proves an
  unauthenticated request is redirected. Security boundary with no regression net.
- **P0-2** `[V]` `trackflow_auth` verifier has no dedicated tests — shared gate for all services;
  failure branches unproven (auth standard §17).
- **P0-3** `[V]` BFF proxy unguarded `fetch` — upstream-down (`ECONNREFUSED`) or hung returns HTML 500
  the client can't parse; no timeout; talent route proxies a **third-party** API. Most likely
  production failure mode (`error-handling.md` §5). Fix: try/catch → JSON 503 + timeout.
- **P0-4** `[V]` No Next.js error boundaries (`error.tsx`/`global-error.tsx`/`not-found.tsx`) and
  `getServerSessionUser` not fail-safe — identity down throws the whole protected tree to Next's
  default error screen.
- **P1-1** `[V]` Three BFF proxy routes (incidents/suppliers/talent) at 0% coverage.
- **P1-2** `[V]` Near-total absence of logging/audit (3 statements backend-wide; 0 frontend) incl.
  **silent token-reuse revocation** and unlogged 5xx/auth-denials/admin actions (`observability.md`).
- **P1-3** `[V]` Remaining missing timeouts (other frontend fetches + Resend) and no global FastAPI
  exception handler (logs detail server-side, returns uniform safe 500).
- **P1-4** `[V]` No rate limiting/lockout on login/reset/refresh (auth standard §10, scoped here).
- **P1-5** `[V]` `errors.ts`/client auth flow (`api.ts`, `context.tsx`) untested — drives all form errors.
- **P2-1** `[V]` Storage-failure wrapping (TinyDB → typed 503/500) **and write serialization** — add
  `RLock` to supplier/incident repos (only identity has one); guard `datetime.fromisoformat` on stored values.
- **P2-2** `[V]` Supplier creation has no uniqueness → 409 (inconsistent with identity's pattern).
- **P2-3** `[V]` No CSP/security headers on back-office (auth standard §9).
- **P2-4** `[V]` Domain logic (`scoring.ts`, supplier/talent API clients) untested; identity `email.py`
  failure path, supplier `seed.py`.
- **P2-5** `[V]` Client `parseAPIError` ignores object-shaped `detail` — incident CSV errors never reach
  the user; also stop rendering raw upstream `detail`/`message` strings (normalize by status/code).
- **P2-6** `[V]` Supplier `/contact` reveal not permission-scoped/audited; least-privilege + audit event.
- **P2-7** `[V]` Incident upload has no size/content-type guard (reads whole file into memory).
- **P2-8** `[R]` Wire CI (`ci.yml`/`e2e.yml`/`security.yml`) per `.github/workflows/README.md` —
  **decision-gated** (task forbids creating workflows now).
- **P3-1** `[V]` `uis/website` has no tests (retirement-flagged — confirm before investing).
- **P3-2** `[R]` Correlation IDs / structured logging / monitoring (platform observability §4).
- **P3-3** `[V]/[R]` (Separate engagement) TinyDB → SQL source-of-truth migration (auth standard §4/§12);
  this also closes the **JWT revocation-lag** (services authorize on claims with no per-request
  user/session reload — acceptable today only because access tokens are 15-min).
- **P3-4** `[A]` UI maps 422 → not-found on detail pages; distinguish once the validation envelope is safe.

## 9. Phased implementation plan (for a later, approved engagement)

**Phase 1 — Confirmed leak + auth/BFF resilience safety net (P0).** Smallest, highest-impact fixes + tests.
- **Stop the 422 input leak:** add a shared custom `RequestValidationError` handler to all three FastAPI
  services returning field name + safe message only (no `input`/`ctx`); tests assert a too-short
  password / bad email / token field never appears in the response body or logs (`caplog`). Reuse one
  helper across services to keep the envelope identical.
- **Harden `proxy.ts`:** wrap `fetch` in try/catch → JSON **503** `{detail:"Service temporarily
  unavailable"}` on connection failure; add `AbortSignal.timeout(...)` → **504** on hang. Tests for
  upstream-down and upstream-hang.
- **Add Next.js error boundaries** — `app/global-error.tsx`, `(protected)/error.tsx`, `not-found.tsx`;
  make `getServerSessionUser` fail safe (identity-down → treat as logged-out/degraded, not a thrown tree).
- Dedicated `packages/trackflow_auth` test suite: valid/expired/tampered/wrong-`alg`/wrong-`aud`/
  missing-claim/`alg:none`/non-access-token → all rejected; CSRF match/mismatch.
- Back-office: protected-layout redirect when unauthenticated/invalid `/auth/me`; `getServerSessionUser`
  success/none/error; assert no token leaks (mirror `caplog` precedent in spirit).
- *Coverage:* no decrease from baseline; **critical auth/BFF paths → ≥90% line / ≥85% branch.**

**Phase 2 — Logging/audit + boundary hardening + core workflows (P1).** Per
`.agents/rules/testing-error-handling-ci.md` (tests in the same change as behavior).
- Add module loggers + handled-failure logging + auth/audit events across all three services —
  explicitly log **token-reuse family revocation**, failed logins, authorization denials, admin
  mutations, and all 5xx, with a correlation ID and **no secrets/PII**; `caplog` sensitive-data
  assertions everywhere new logging lands.
- Add one global FastAPI exception handler per service (safe generic 500, detail logged server-side,
  correlation ID) with tests; add remaining `fetch` timeouts + Resend timeout.
- Add rate limiting/lockout to login/reset/refresh with tests (auth standard §10/§17).
- Test the three BFF proxy routes; client auth flow (`api.ts`, `context.tsx`); `errors.ts` field-error
  mapping; supplier/incident/talent/account workflows.
- *Coverage:* set an enforceable per-app back-office floor from the measured post-Phase-1 baseline.

**Phase 3 — General hardening + platform (P2–P3).**
- Wrap TinyDB calls as typed storage errors → 503/500 with tests; **add `RLock` to supplier/incident
  repositories**; guard `datetime.fromisoformat` on stored values (→ controlled auth failure, not 500).
- Add supplier uniqueness check → **409** (match identity's `DuplicateEmailError` pattern), with tests.
- Teach client `parseAPIError` to read object-shaped `detail` (incident CSV errors) and normalize
  display by status/code instead of rendering arbitrary upstream strings.
- Permission-scope + audit the supplier `/contact` reveal; add incident upload size/content-type guard
  with controlled pre-parse errors.
- CSP + security headers on back-office (`next.config.ts headers()`); domain-logic unit tests
  (`scoring.ts`, API clients), `email.py` failure path, `seed.py`.
- *Coverage:* ratchet general production code → **≥80% line / ≥75% branch**; do not force low-risk
  presentational components to 90%.
- **Decision-gated:** CI workflows, correlation IDs/structured logging/monitoring, SQL migration
  (separate engagement). Reconcile the docs/health-endpoint discrepancy (§6).

## 10. Acceptance criteria & validation commands per phase

**Phase 1 acceptance:** a 422 on any service returns field name + safe message with **no submitted
value** in body or logs (re-run the reset-password probe → `input` absent); new `trackflow_auth` suite
passes; back-office auth-gate/session tests pass; proxy returns JSON **503** on upstream-down and **504**
on hang (asserted, not HTML); error boundaries render and `getServerSessionUser` fails safe when identity
is down; back-office overall coverage ≥ baseline and critical paths ≥90% line/≥85% branch; no
secrets/tokens in any asserted log/response.
```
uv run --project services/identity --extra dev pytest          # transitive auth still green
(cd packages/trackflow_auth && uv run --with pytest --with pytest-cov pytest)   # new suite
npm run test --workspace uis/backoffice
npx vitest run --coverage --workspace uis/backoffice           # critical-path thresholds
```
**Phase 2 acceptance:** BFF route + client-auth + workflow tests pass; new logging covered by `caplog`
sensitive-data assertions; global 500 handler returns generic body (asserted) and logs detail;
rate-limit tests pass; per-app back-office floor enforced and not regressed.
```
uv run --project services/incident-processor --extra dev pytest
uv run --project services/supplier-directory --extra dev pytest
npm run test --workspace uis/backoffice
npm run test:e2e --workspace uis/backoffice                    # auth-smoke against ephemeral services
```
**Phase 3 acceptance:** storage-failure tests return 503/500 with safe message; supplier/incident repos
serialize writes (`RLock`) and duplicate supplier → 409; client surfaces incident dict-`detail` errors and
no longer renders raw upstream strings; supplier `/contact` requires the named permission and emits an
audit event; incident upload rejects oversized/wrong-type files before parsing; CSP/security headers
present (asserted in response headers); general coverage ≥80% line/≥75% branch per app; full gate green.
```
# all of the above, plus per-touched-app:
npm run type-check --workspace uis/backoffice && npm run build --workspace uis/backoffice && npm run lint --workspace uis/backoffice
```
Every phase also clears the `production-readiness.md` §1 release gates (lint+type-check, build, tests +
coverage preserved, failure paths handled, no sensitive data logged, docs that move together updated).

## 11. Decisions that require approval

0. **Production blocker confirmed** — the 422 input-echo leak (P0-0) is a hard release blocker under
   `production-readiness.md` §1.5; recommend authorizing the Phase-1 fix even ahead of the broader
   engagement. Confirm this is treated as blocking.
1. **CI automation** `[R]` — `ci.yml`/`e2e.yml`/`security.yml` + coverage gate + branch protection are
   the natural enforcement for the ratchet, but the task forbids creating workflows now. Approve a
   follow-up engagement to implement `.github/workflows/README.md`’s checklist? (Until then, gates stay
   reviewer-enforced.)
2. **SQL migration** — confirmed **separate engagement**; needs scheduling/owner. Approve as its own brief?
3. **Enforceable coverage floors** — confirm the concrete per-app numbers (Phase-1 critical ≥90/85,
   Phase-3 general ≥80/75) and that the post-Phase-1 baseline sets the interim back-office floor.
4. **`uis/website` testing** `[?]` — confirm the retirement timeline before deciding whether to add any
   test infrastructure (current `[R]`: minimal/none).
5. **Adding `pytest-cov` / `@vitest/coverage-v8` as real devDependencies** — required to enforce
   coverage in CI; this plan only used them ephemerally. Approve persisting them when implementation begins.
6. **Docs correction** — update `observability.md` §4 / `runbooks/README.md` to reflect that `/health`
   endpoints already exist (still unmonitored). Approve as part of Phase 3 docs updates.
