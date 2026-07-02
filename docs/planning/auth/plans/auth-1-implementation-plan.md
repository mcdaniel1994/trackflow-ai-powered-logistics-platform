# Auth 1 — Implementation Plan: Backend Authentication + API Route Protection

**Status:** Planning (no code written). **Phase:** 1 of 3. **Requirements:** `docs/planning/auth/auth-1-backend-api-requirements.md`. **Decisions:** `docs/planning/auth/auth-security-decisions.md`. **Standard:** `docs/standards/authentication-security-standard.md`.

> **Phase gate:** Auth 1 must be implemented, tested, reviewed, and approved before Auth 2 begins. Password-reset persistence/email is **not** in this phase (Auth 3 only).

---

## 1. Objective and Scope

Introduce a dedicated **identity service** providing user management, password hashing, login/refresh/logout, JWT access tokens, and reusable authentication/authorization dependencies; and **protect the existing domain APIs** (`supplier-directory`, `incident-processor`) so they reject unauthenticated requests.

**In scope:** identity service (`services/identity`); TinyDB-backed `users` + `refresh_sessions`; Argon2id hashing; RS256 access tokens; rotating refresh tokens with server-side revocation; `get_current_user` + authorization dependencies; admin-only user creation with temporary password; first-admin CLI; token validation in the two domain services; route-classification table; backend tests; production deployment gate.

**Out of scope (later phases):** any frontend pages/state (Auth 2); password reset, email, `password_resets` collection (Auth 3); role-editing; rate limiting; audit logging; SQL/migrations.

**Expected side effect:** once domain APIs are protected, the current `uis/backoffice` calls will return `401` until Auth 2 wires authentication. This is expected per the Auth 1 requirements.

---

## 2. Relevant Repository Findings (exact paths)

- Existing FastAPI + TinyDB service to mirror: `services/supplier-directory/supplier_directory/` — `main.py`, `service.py`, `repository.py`, `models.py`, `config.py`, `constants.py`, `seed.py`; tests in `services/supplier-directory/tests/test_api.py`; packaging `services/supplier-directory/pyproject.toml`; env `services/supplier-directory/.env.example`.
- Second service to protect: `services/incident-processor/incident_processor/main.py` (stateless, port 8000).
- TinyDB repository pattern: `services/supplier-directory/supplier_directory/repository.py` (TinyDB + `Query`, `uuid4` ids).
- Pydantic model + `model_config = ConfigDict(extra="forbid")` patterns: `services/supplier-directory/supplier_directory/models.py`.
- Config-from-env pattern: `services/supplier-directory/supplier_directory/config.py` (`os.getenv`, defaults).
- Test pattern: `services/supplier-directory/tests/test_api.py` (`TestClient`, `monkeypatch.setenv` for DB path, `tmp_path`).
- Monorepo root pytest scoping: `conftest.py` (uses `importlib.util.find_spec` per service).
- **No existing auth/JWT/hashing code or deps** anywhere in `services/` or `packages/`.

---

## 3. Proposed Design

A new `services/identity` FastAPI app mirroring the supplier-directory layering: **routes → services → repository interfaces → TinyDB implementations**. Security primitives (hashing, JWT sign/verify, cookies, CSRF) live in `security.py`; FastAPI dependencies in `dependencies.py`. A shared, minimal token-**verification** helper is reused by the domain services (they hold only the public key).

### Token & session model
- **Access token:** RS256 JWT, `exp` 15 min, claims: `sub` (user id), `role`, `iss`, `aud`, `iat`, `jti`, `token_type="access"`. Delivered as an HttpOnly cookie.
- **Refresh token:** opaque random value delivered as a separate HttpOnly cookie; stored **hashed** in `refresh_sessions` with `user_id`, `family_id`, `expires_at` (14 days), `revoked`. On `/auth/refresh`, rotate (issue new, mark old used); presenting a rotated-out/used token → revoke the whole `family_id`.
- **CSRF:** double-submit — a non-HttpOnly CSRF cookie + matching `X-CSRF-Token` header required on state-changing requests; verified server-side.
- **Validation every request:** verify signature (public key), `exp`, `iss`, `aud`, `alg=RS256`; reject `alg:none` and any client-chosen algorithm; load the user from TinyDB; require `status="active"`.

### Authorization
- `get_current_user` → validated, active user.
- `require_admin` → 403 unless `role="admin"`.
- `self_or_admin(user_id)` → 403 unless target is the caller or caller is admin (prevents IDOR).
- `require_password_current` → while `must_change_password=true`, only `/auth/me`, `/auth/change-password`, `/auth/logout` are permitted; everything else → 403 with a clear "password change required" detail.

---

## 4. Files to Create

Under `services/identity/` (mirroring supplier-directory packaging):

- `pyproject.toml` — package `trackflow-identity`, deps in §10, `[tool.pytest.ini_options]` like the existing services.
- `.env.example` — placeholders only (see §9).
- `README.md` — run/test instructions, single-worker note.
- `identity/__init__.py`
- `identity/config.py` — env loading (keys, token lifetimes, cookie flags, CORS, DB path, issuer/audience).
- `identity/constants.py` — roles (`user|admin`), statuses (`active|suspended|disabled`), cookie names, token types.
- `identity/models.py` — Pydantic: `UserCreate` (admin input: name, email), `UserPublic` (safe fields), `UserUpdate`, `LoginRequest`, `ChangePasswordRequest`, `TokenClaims`, `AdminStatusUpdate`. `UserPublic` **never** includes any hash/secret.
- `identity/security.py` — Argon2id hash/verify; temp-password generator; RS256 sign/verify with full claim checks; refresh-token generation + hashing; CSRF token helpers; cookie set/clear helpers (env-driven flags).
- `identity/repository.py` — `UserRepository`, `SessionRepository` as interfaces (ABC/Protocol) + `TinyDBUserRepository`, `TinyDBSessionRepository`. Email normalization + uniqueness; stable `uuid4` ids; UTC ISO timestamps; write coordination; expired-session cleanup.
- `identity/service.py` — `UserService` (create-with-temp-password, get, list, update, soft-disable, set status, normalize/validate email, enforce uniqueness), `AuthService` (login, refresh-rotate, logout, change-password, build claims, revoke-all-for-user).
- `identity/dependencies.py` — `get_current_user`, `require_active`, `require_admin`, `self_or_admin`, `require_password_current`, CSRF dependency.
- `identity/main.py` — FastAPI app, CORS (`allow_credentials=True`, explicit origins), routers for `/auth` and `/users`, `/health` (public).
- `identity/cli.py` — `create-admin` command (`python -m identity.cli create-admin`).
- `identity/tests/test_auth.py`, `identity/tests/test_users.py`, `identity/tests/test_security.py`, `identity/tests/test_cli.py`, `identity/tests/test_domain_protection.py` (or per-service equivalents — see §11).

Shared token verification helper (choose one; recommend the package approach for reuse): `packages/` Python module `trackflow_auth` (verify-only: public-key claim validation), or a small `security.py` copied into each domain service. The plan recommends a **single reusable verify module** to avoid drift.

---

## 5. Files to Modify

- `services/supplier-directory/supplier_directory/main.py` — add an auth dependency that validates the access-token cookie/bearer using the **public key** and rejects unauthenticated requests on all business endpoints (keep `/health` public). Add the dependency to: `POST /suppliers`, `GET /suppliers`, `GET /suppliers/{id}`, `GET /suppliers/{id}/contact`, `PATCH .../rate`, `PATCH .../status`, `DELETE /suppliers/{id}`.
- `services/supplier-directory/supplier_directory/config.py` + `.env.example` — add `IDENTITY_JWT_PUBLIC_KEY`, `IDENTITY_JWT_ALGORITHM`, issuer/audience; review CORS (`allow_credentials` stays as needed; the BFF, not the browser, will call these in Auth 2).
- `services/incident-processor/incident_processor/main.py` + `config.py` + `.env.example` — same token-validation wiring on its business endpoints (keep `/health` public).
- `services/supplier-directory/pyproject.toml` and `services/incident-processor/pyproject.toml` — add the verify dependency (`python-jose[cryptography]` or the shared `trackflow_auth` package).
- Root `conftest.py` — extend the `find_spec` scoping logic to include `identity` so root-level pytest collection stays scoped.
- `services/README.md` — add the identity service entry.

> **Protected-paths note (AGENTS.md):** these are integration-only metadata/wiring changes within the active engagement; no delivered brief or `packages/shared/` product code is rewritten. Engagement-tracking docs (README roadmap, memory-bank, brief status) are updated per the pre-commit workflow when implementation lands.

---

## 6. Database / Persistence Changes (TinyDB)

New TinyDB database for identity (path from env, default under `services/identity/data/identity.json`). Collections:

- `users`: `id`, `email` (normalized lowercase, unique — enforced in repository + service), `hashed_password` (Argon2id), `name`, `role` (`user|admin`), `status` (`active|suspended|disabled`), `must_change_password` (bool), `created_at` (UTC ISO), `last_login_at` (UTC ISO|null).
- `refresh_sessions`: `id`, `user_id`, `token_hash`, `family_id`, `expires_at` (UTC ISO), `revoked` (bool), `created_at`, `rotated_from` (id|null).

**TinyDB safeguards (documented limitations):** normalize emails before store/compare; enforce uniqueness in repository + service (no DB constraint); generated stable ids (never rely on TinyDB doc positions); UTC ISO timestamps; make writes as atomic as reasonably possible and coordinate writes at the repository layer; **identity service runs single-worker** until SQL or a tested file-locking strategy is added; address concurrent refresh-rotation, session-revocation, and duplicate-email races and document any residual limitation; backup/corruption considerations noted; expired-session cleanup routine. **No claim** of SQL-level transactions/concurrency. Reset records are **not** created here (Auth 3).

---

## 7. API Changes

All identity routes on the new service. **`/auth/register` does not exist.**

### `/auth`
- `POST /auth/login` — body `{email, password}`; verify Argon2id; require `status="active"`; set HttpOnly access + refresh cookies + CSRF cookie; update `last_login_at`; generic error on failure (no enumeration).
- `POST /auth/refresh` — read refresh cookie; validate + rotate; reuse/rotated-out → revoke family → 401; set new cookies.
- `POST /auth/logout` — revoke the current refresh session server-side; clear cookies.
- `GET /auth/me` — protected; returns `UserPublic` (id, name, email, role, status, `must_change_password`, created_at, last_login_at).
- `POST /auth/change-password` — protected; re-auth with current password; set new Argon2id hash; set `must_change_password=false`; revoke all **other** sessions; (also the only privileged action allowed while `must_change_password=true`).

### `/users` (admin-controlled)
- `POST /users` — **admin only**; body `{name, email}`; create `role="user"`, `status="active"`; generate strong temp password; store only its Argon2id hash; set `must_change_password=true`; return `UserPublic` **plus the temporary password exactly once** (documented one-time field, never logged/redisplayed).
- `GET /users` — **admin only**; list `UserPublic`.
- `GET /users/{id}` — **self-or-admin**.
- `PUT /users/{id}` — **self-or-admin**; update `name` (email-change policy: out of scope unless approved); never accepts `role`/`status`/hash from clients.
- `PATCH /users/{id}/status` — **admin only**; `active|suspended|disabled`; on suspend/disable revoke all the user's refresh sessions immediately.
- `DELETE /users/{id}` — **admin only**; **soft-disable** (`status=disabled`) + revoke sessions; not a hard delete.

### Domain services
- `supplier-directory` + `incident-processor`: all business endpoints become **Authenticated**; `/health` stays **Public**.

### Suspension semantics
On suspend/disable: revoke refresh sessions; reject future login + refresh; issue no new access tokens. An already-issued access token may remain valid up to ≤15 min (accepted, documented). No introspection/denylist now.

### Route Classification Table (all three services)

| Service | Method + path | Classification |
|---|---|---|
| identity | `GET /health` | Public |
| identity | `POST /auth/login` | Public |
| identity | `POST /auth/refresh` | Public (cookie-bearing) |
| identity | `POST /auth/logout` | Authenticated |
| identity | `GET /auth/me` | Authenticated |
| identity | `POST /auth/change-password` | Authenticated (allowed while must_change_password) |
| identity | `POST /users` | Admin-only |
| identity | `GET /users` | Admin-only |
| identity | `GET /users/{id}` | Self-or-admin |
| identity | `PUT /users/{id}` | Self-or-admin |
| identity | `PATCH /users/{id}/status` | Admin-only |
| identity | `DELETE /users/{id}` | Admin-only (soft-disable) |
| supplier-directory | `GET /health` | Public |
| supplier-directory | `POST /suppliers` | Authenticated |
| supplier-directory | `GET /suppliers` | Authenticated |
| supplier-directory | `GET /suppliers/{id}` | Authenticated |
| supplier-directory | `GET /suppliers/{id}/contact` | Authenticated |
| supplier-directory | `PATCH /suppliers/{id}/rate` | Authenticated |
| supplier-directory | `PATCH /suppliers/{id}/status` | Authenticated |
| supplier-directory | `DELETE /suppliers/{id}` | Authenticated |
| incident-processor | `GET /health` | Public |
| incident-processor | all business endpoints (analyze/export/latest) | Authenticated |

> Any future endpoint is **deny-by-default**: protected until explicitly classified Public.

---

## 8. Frontend Changes

**None in Auth 1.** All UI work is Auth 2. (Expect the current backoffice to receive `401` from protected APIs until then.)

---

## 9. Environment Variables

Identity service `.env.example` (placeholders only — never commit real secrets):

```
IDENTITY_JWT_PRIVATE_KEY=        # RS256 private key (identity service ONLY)
IDENTITY_JWT_PUBLIC_KEY=         # RS256 public key (all verifiers)
IDENTITY_JWT_ALGORITHM=RS256
IDENTITY_JWT_ISSUER=trackflow-identity
IDENTITY_JWT_AUDIENCE=trackflow-backoffice
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=14
IDENTITY_DB_PATH=services/identity/data/identity.json
IDENTITY_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
AUTH_COOKIE_SECURE=false         # false ONLY for local http://localhost; true in production
AUTH_COOKIE_SAMESITE=lax
```

Domain services add `IDENTITY_JWT_PUBLIC_KEY`, `IDENTITY_JWT_ALGORITHM`, `IDENTITY_JWT_ISSUER`, `IDENTITY_JWT_AUDIENCE` to their `.env.example`. Key generation: document `openssl`-based RS256 keypair generation in the identity README; private key only ever in the identity environment.

---

## 10. Dependencies (documented; install only at implementation time)

Identity service: `fastapi`, `uvicorn[standard]`, `tinydb` (as existing), plus `python-jose[cryptography]` (RS256), `passlib[argon2]` or `argon2-cffi` (Argon2id), `python-multipart` (form login if used). Dev: `httpx`, `pytest`. Domain services: add `python-jose[cryptography]` (or the shared `trackflow_auth` verify package).

---

## 11. Testing Plan

Use the existing pytest + `TestClient` pattern; per-test isolated TinyDB via `monkeypatch.setenv(IDENTITY_DB_PATH, tmp_path/...)`; generate a throwaway RS256 keypair in a fixture.

Cover (Auth 1 requirements §11 + standard §17):
- Admin user creation returns a one-time temp password + `must_change_password=true`; duplicate email rejected; email normalized.
- Argon2id hashing + verification; temp password never present in `UserPublic`/logs.
- Login success / invalid email / invalid password (generic error); suspended/disabled cannot log in.
- Access-token creation; valid-token access; missing/malformed/invalid-signature/expired/wrong-`alg`/wrong-`aud`/unknown-user → 401.
- `must_change_password` lockout: protected business calls → 403 until changed; change-password clears it and revokes other sessions.
- Refresh rotation; rotated-out/reused refresh → family revoked → 401.
- Logout revokes session server-side.
- Authorization: `GET /users` admin-only (403 for normal user); `GET/PUT /users/{id}` self-or-admin (403 + no-IDOR for another user's id); `PATCH status` + `DELETE` admin-only; `DELETE` soft-disables (record persists with `status=disabled`).
- Suspension revokes refresh sessions; subsequent refresh/login rejected.
- Response never leaks any hash/secret (assert absence).
- CLI `create-admin`: creates admin, refuses duplicate, never prints/stores raw password.
- Domain protection: unauthenticated call to each protected supplier/incident endpoint → 401; authenticated (valid token) → succeeds; `/health` stays public.

---

## 12. Manual Verification

Identity `/docs` flow plus domain checks:
1. `python -m identity.cli create-admin` → create the first admin.
2. `POST /auth/login` as admin → cookies set.
3. `POST /users` (admin) → capture the one-time temp password.
4. Log in as the new user → `GET /auth/me` shows `must_change_password=true`; a protected business call returns 403.
5. `POST /auth/change-password` → succeeds; `must_change_password=false`.
6. Re-call the protected route → succeeds.
7. Remove/expire/malform the token → 401 each.
8. As a normal user, call `GET /users` → 403; call another user's `GET /users/{id}` → 403.
9. Admin `PATCH /users/{id}/status` suspend → that user's refresh fails.
10. Directly call `supplier-directory` `GET /suppliers` with no token → 401; with a valid token → 200; `GET /health` → 200 without a token.

---

## 13. Acceptance Criteria

- Identity service exists with TinyDB `users` + `refresh_sessions` behind repository interfaces.
- Passwords hashed with **Argon2id**; plaintext never stored/logged/returned.
- Login issues an RS256 access cookie (15 min) + rotating refresh cookie (14 days); refresh rotation + family revocation work.
- `/auth/me` returns only safe fields incl. `must_change_password`.
- `get_current_user` + `require_admin` + `self_or_admin` reusable; protected routes reject unauthenticated (401) and unauthorized (403) callers; no IDOR.
- **`/auth/register` does not exist**; admin-only `POST /users` is the sole creation path with a one-time temp password and forced change.
- First admin creatable only via CLI.
- Suspend/disable revokes sessions; soft-disable for `DELETE`.
- `supplier-directory` and `incident-processor` reject unauthenticated requests; `/health` public; route-classification table reflected in code.
- Asymmetric RS256: only identity holds the private key.
- All config from env; `.env.example` placeholders only; no secrets committed.
- Automated tests pass; manual `/docs` + domain flow succeeds.
- **No frontend work** mixed into this phase.
- **Production Authentication Deployment Checklist** satisfied before any hosted deployment.

### Production Authentication Deployment Checklist (deployment gate)
`Secure=false` only on local `http://localhost`; hosted requires `Secure=true` + HTTPS.
- [ ] HTTPS enabled · [ ] cookies `Secure=true` · [ ] `HttpOnly=true` kept · [ ] `SameSite=Lax` kept · [ ] no broad cookie `Domain` (host-only) · [ ] correct prod frontend/service URLs · [ ] dev secrets + RS256 keys replaced with prod secrets · [ ] secrets only in deployment env (not committed) · [ ] reverse proxy recognizes HTTPS (forwarded-proto) · [ ] trusted origins/CORS without wildcard+credentials · [ ] post-deploy test of login/refresh/logout/CSRF/protected-routes/cookies.

---

## 14. Implementation Checklist

- [ ] Scaffold `services/identity` (packaging, config, constants, README).
- [ ] `security.py`: Argon2id, RS256 sign/verify, refresh hashing, CSRF, cookie helpers, temp-password generator.
- [ ] `repository.py`: interfaces + TinyDB users/sessions with safeguards.
- [ ] `service.py`: `UserService` + `AuthService`.
- [ ] `dependencies.py`: current-user + authz + must-change-password lockout.
- [ ] `main.py`: `/auth` + `/users` routers, CORS, `/health`.
- [ ] `cli.py`: `create-admin`.
- [ ] Shared verify helper (`packages/trackflow_auth` recommended).
- [ ] Wire token validation into `supplier-directory` and `incident-processor`; update their config/`.env.example`/`pyproject.toml`.
- [ ] Update root `conftest.py`, `services/README.md`.
- [ ] Tests per §11; manual verification per §12.
- [ ] Update engagement-tracking docs per AGENTS.md pre-commit workflow.

---

## 15. Decisions Requiring Approval (carried from the decision record)

- Key-rotation procedure/cadence for the RS256 keypair (default: documented manual rotation).
- Email-change policy on `PUT /users/{id}` (default: out of scope this phase).
- Whether login rate limiting/lockout is added now or deferred (default: deferred, optional).
- Shared verify module location: `packages/trackflow_auth` (recommended) vs per-service copy.

---

## 16. Approval Gate

**Do not begin Auth 2 until Auth 1 is implemented, tested, reviewed, and approved.** No Auth 2 (frontend) or Auth 3 (reset/email) work may be folded into this phase. The single documented cross-phase item delivered here for downstream use is the `change-password` endpoint and the `name`/`must_change_password` model fields (Auth 2 dependencies), per the decision record.
