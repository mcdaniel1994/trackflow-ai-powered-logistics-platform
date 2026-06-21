# TrackFlow Authentication — Security Decision Record

**Status:** Auth 1-3 implemented locally. **Owner:** Cory McDaniel. **Last updated:** 2026-06-20.

This is the authoritative decision log for TrackFlow authentication (Auth 1, Auth 2, Auth 3). It is referenced by:

- `docs/planning/auth/plans/auth-1-implementation-plan.md`
- `docs/planning/auth/plans/auth-2-implementation-plan.md`
- `docs/planning/auth/plans/auth-3-implementation-plan.md`

It is tied directly to this repository: the three requirement files in `docs/planning/auth/`, the standard `docs/standards/authentication-security-rule.md`, the FastAPI services in `services/`, the Next.js app in `uis/backoffice`, the public site in `uis/website`, the existing TinyDB persistence, and the existing pytest setup.

---

## 1. Decision Summary

Where the three authentication **requirement files conflict with `docs/standards/authentication-security-rule.md`, the security rule wins.** TrackFlow is being built as a production application, so it adopts the production-oriented posture: Argon2id hashing, HttpOnly/Secure/SameSite cookies (never `localStorage`), short-lived access tokens with rotating refresh tokens, a server-side revocation store, CSRF protection, and backend-enforced authorization. Persistence stays on the repo's existing **TinyDB** for now (SQL is deferred to a future engagement) but is hidden behind repository interfaces so the later SQL migration does not rewrite the auth API or services.

Every requirement that was superseded is documented in §2 and §6 — none were silently changed.

---

## 2. Conflicting Requirements

| # | Requirement-file instruction | `authentication-security-rule.md` | Resolution |
|---|---|---|---|
| C1 | **bcrypt** via passlib (Auth 1 §"Required Approach", §13) | §5/§8: **Argon2id** preferred; bcrypt only "acceptable for legacy" | **Argon2id** |
| C2 | Store JWT in **`localStorage`** (Auth 2 §5) | §5/§15: never `localStorage`/`sessionStorage` | **HttpOnly cookie**, no web storage |
| C3 | **Bearer-token only, no cookies** (Auth 1 §"Required Approach") | §6: token-in-cookie / server session recommended | **HttpOnly cookie** transport |
| C4 | **Completely stateless JWT** (Auth 1 §"Required Approach") | §7: server-side revocation; refresh rotation | **Stateless short access token + server-side refresh/revocation store** |
| C5 | **Client-side logout** (remove token) implied (Auth 2 §7) | §7/§16: logout/password-change must invalidate server-side | **Server-side session revocation** on logout/password-change/suspend |

Supporting conflicts surfaced during planning (not in the matrix above but resolved the same way): the requirements assume a **SQL database with migrations** (the repo has only TinyDB — see §3/Decision D2); the requirements list **`POST /users` and `POST /auth/register`** as separate user-creation endpoints (resolved to a single admin-only `POST /users` — Decision D4); the **minimum user model lacks `name`** though Auth 2 needs it (added — Decision D11).

---

## 3. Final Decisions

The authentication posture selected for TrackFlow:

- **Hashing:** Argon2id (via `argon2-cffi`/`passlib`).
- **Access token:** short-lived JWT, **15 minutes**, **RS256 asymmetric** signing.
- **Refresh token:** rotating, **14 days**, stored **hashed** server-side with a token-family id; reuse of a rotated-out token revokes the whole family.
- **Transport:** HttpOnly, Secure (prod), SameSite=Lax, host-only (no `Domain`) cookies. Dev over `http://localhost` uses `Secure=false`.
- **CSRF:** double-submit token + SameSite for cookie-authenticated state-changing requests.
- **Authorization:** backend-enforced on every protected endpoint; `role = user|admin`; `status = active|suspended|disabled`; ownership/self-or-admin checks (no IDOR).
- **Revocation:** server-side; logout, password change, and suspend/disable revoke refresh sessions immediately.
- **Persistence:** TinyDB now (users + refresh sessions in Auth 1; password-reset records in Auth 3), behind repository interfaces; SQL deferred.
- **Frontend:** Next.js BFF / same-origin proxy in `uis/backoffice`; browser talks only to the Back Office origin.
- **Registration:** none public — administrator-controlled creation via `POST /users`; first admin via CLI.

The full per-decision register is in Decisions D1–D17 below.

---

## 4. Reasons for the Decisions

1. **Token theft resistance.** Tokens in `localStorage` are readable by any JavaScript on the origin; one XSS or one compromised dependency leaks them. HttpOnly cookies are not script-readable, narrowing the blast radius.
2. **Stronger password hashing.** Argon2id is memory-hard and the current OWASP-preferred choice for new applications; bcrypt remains acceptable but weaker for a greenfield build.
3. **Real logout / session invalidation.** Pure stateless JWTs cannot be revoked before expiry. A server-side refresh/session store lets logout, password change, and account suspension take effect immediately for refresh, with a bounded ≤15-minute window on already-issued access tokens.
4. **Refresh-token theft detection.** Rotation + family tracking detects reuse of a stolen, rotated-out token and kills the session family.
5. **Better long-term architecture.** This foundation supports later features: admin controls, "log out everywhere", active-session management, suspension, secure password reset, audit logging, and AI agents acting in a decided permission context.
6. **Backend stays the boundary.** The frontend never decides identity or permissions; route guards and hidden nav are UX only.

---

## 5. Tradeoffs Accepted

The chosen posture is more complex than the literal requirements. Accepted because TrackFlow is production-oriented:

- CSRF protection (double-submit) must be implemented and tested.
- Cookie configuration differs per environment (a production deployment gate mitigates the risk — §7 / Decision D14).
- A server-side session/refresh store must be persisted (extra TinyDB collection) and cleaned up.
- Refresh-token rotation, family tracking, and revocation logic add code and tests.
- The BFF proxy adds a routing layer and some deployment complexity in `uis/backoffice`.
- TinyDB gives no SQL-level transactions/constraints; the identity service runs **single-worker** until SQL or tested file locking (Decision D2). This is a scoped, temporary compromise.

---

## 6. Requirements Superseded

| Original requirement | Replaced by |
|---|---|
| bcrypt | Argon2id |
| JWT in `localStorage` | JWT in HttpOnly cookie |
| Bearer-only, no cookies | Cookie transport + CSRF |
| Stateless JWT only | Short access token + server-side refresh/revocation |
| `POST /auth/register` (public) | **Removed.** Admin-only `POST /users` is the sole creation endpoint |
| Separate `POST /users` and `/auth/register` | Single admin-only `POST /users` |
| Minimum user model without `name` | `name` added |
| SQL database + migrations (assumed) | TinyDB behind repository interfaces; SQL deferred to Engagement 5 |

---

## Decision Register (D1–D17)

Each decision records: **Question/Conflict · Decision · Why · Security/Architecture advantages · Tradeoffs accepted · Phase owner · Deferred · Supports SQL migration.**

### D1 — Security posture
- **Question/Conflict:** Follow the requirement files (bcrypt, localStorage, stateless) or the security rule? (C1–C5)
- **Decision:** Follow `authentication-security-rule.md`.
- **Why:** TrackFlow is production-bound, not a throwaway demo.
- **Advantages:** Token-theft resistance, real revocation, modern hashing.
- **Tradeoffs:** CSRF, cookies, session store, more tests.
- **Phase owner:** Auth 1 (backend), Auth 2 (frontend), Auth 3 (reset).
- **Deferred:** —
- **Supports SQL migration:** Server-side revocation maps cleanly onto a future `refresh_sessions` SQL table.

### D2 — Persistence stays TinyDB, behind interfaces
- **Question/Conflict:** Requirements assume SQL + migrations; repo has only TinyDB.
- **Decision:** Keep TinyDB. Auth records live behind `UserRepository` / `SessionRepository` (Auth 1) and `PasswordResetRepository` (Auth 3) interfaces. **Identity service runs single-worker.**
- **Why:** SQL is intentionally deferred (likely Engagement 5); avoid scope creep.
- **Advantages:** No new infra; matches existing `services/supplier-directory` pattern.
- **Tradeoffs:** No SQL transactions/constraints/indexes; concurrency handled by single-worker + repository write coordination; documented, not hidden.
- **Phase owner:** Auth 1 (users, sessions), Auth 3 (resets).
- **Deferred:** SQLAlchemy repositories + Alembic migrations + data transfer (see "Deferred to future SQL engagement" note below).
- **Supports SQL migration:** Repository boundary lets TinyDB implementations be swapped for SQLAlchemy without changing routes/services; Argon2id hashes transfer without forcing password resets.

> **Deferred to future SQL engagement:** Replace the TinyDB repository implementations with SQLAlchemy repositories, introduce Alembic migrations, transfer existing authentication records safely (users, password hashes, active sessions where appropriate, reset state), add DB constraints and indexes, and verify the migration **without changing the authentication API contract**. PostgreSQL + SQLAlchemy + Alembic are the expected direction but are **not** part of Auth 1–3.

### D3 — Dedicated identity service
- **Question/Conflict:** Which backend hosts `/auth` and `/users`?
- **Decision:** New `services/identity` owning users/auth/sessions; `supplier-directory` and `incident-processor` only validate tokens.
- **Why:** Keeps domain services single-purpose; clean boundaries.
- **Advantages:** One identity source of truth; other services hold no private key.
- **Tradeoffs:** A third service to run/deploy.
- **Phase owner:** Auth 1.
- **Deferred:** —
- **Supports SQL migration:** Only one service's persistence layer changes.

### D4 — Administrator-controlled registration (no public registration; `/auth/register` removed)
- **Question/Conflict:** Requirements list public `/auth/register` and separate `POST /users`.
- **Decision:** **No public registration.** `/auth/register` does **not** exist anywhere (not public, not an admin alias). Administrator-protected **`POST /users`** is the only user-creation endpoint. New users always `role="user"`, `status="active"`; clients never choose a role; the first user is never auto-promoted.
- **Why:** The Back Office is an internal business system; administrators must control who gets access.
- **Advantages:** Smaller attack surface; no unknown-visitor account creation; one non-duplicated contract.
- **Tradeoffs:** Requires the admin Create-User flow + first-admin bootstrap (D5).
- **Phase owner:** Auth 1 (endpoint), Auth 2 (admin UI).
- **Implemented after Auth 3:** Email invitation / one-time set-password link using the Auth 3 reset-token infrastructure. Temporary passwords are never emailed.
- **Supports SQL migration:** Single creation path is simpler to port.

The full administrator-controlled registration flow:
1. First admin created via CLI: `python -m identity.cli create-admin`.
2. Admin signs in at the shared `/login`.
3. Admin opens `/admin/users`.
4. Admin selects **Create User**, enters name + email.
5. Frontend calls admin-protected `POST /users`.
6. Backend: confirms admin → normalizes/validates email → rejects duplicates → creates `role="user"`, `status="active"` → generates a strong temporary password → stores only the Argon2id hash → sets `must_change_password=true` → sends an account setup email with a single-use reset link → returns the temp password **once** as a fallback.
7. User follows the setup link from email and chooses a password, or the admin securely hands off the fallback temp password if email delivery fails.
8. If the user signs in with the fallback temp password, `must_change_password=true` redirects them to `/account/change-password`.
9. Until changed, the user may only view auth state, change password, log out.
10. After change: `must_change_password=false`, issue updated credentials, allow normal access.

### D5 — First-admin bootstrap via CLI
- **Question/Conflict:** With no public registration, how is the first admin created?
- **Decision:** Trusted CLI `python -m identity.cli create-admin` — secure prompt, normalize/validate email, refuse duplicates, Argon2id hash, `role=admin`, `status=active`, never log the raw password, local/server access only.
- **Why:** Needs a trusted initial admin without exposing an admin-creation path on the public API.
- **Advantages:** No network-exposed privilege-escalation path.
- **Tradeoffs:** Requires shell/server access to bootstrap.
- **Phase owner:** Auth 1.
- **Deferred:** —
- **Supports SQL migration:** CLI calls the same repository interface.

### D6 — Single account-status field
- **Question/Conflict:** Use both `is_active` and `status`?
- **Decision:** One field: `status = active|suspended|disabled`. Drop `is_active`. Only `active` may authenticate / use protected routes.
- **Why:** Two fields can contradict (e.g. suspended but `is_active=true`).
- **Advantages:** One authoritative state; easier to validate/test/migrate.
- **Tradeoffs:** —
- **Phase owner:** Auth 1.
- **Deferred:** —
- **Supports SQL migration:** One enum column.

### D7 — Role model + deferred role editing
- **Question/Conflict:** No role/permission model exists; requirements mention an admin.
- **Decision:** Minimal `role = user|admin` with reusable checks (authenticated / admin-only / self-or-admin). **Role-editing UI deferred.**
- **Why:** Resolves admin references without a full RBAC system; promotion is high-impact and needs reauth, audit, and final-admin protection.
- **Advantages:** Small surface now; safe extension later.
- **Tradeoffs:** Admins can't promote via UI yet.
- **Phase owner:** Auth 1 (field + checks), Auth 2 (admin-only nav/pages).
- **Deferred:** Role-editing UI + safeguards (separate approval).
- **Supports SQL migration:** `role` becomes a column or a roles table later.

### D8 — Safe `/auth/me` fields
- **Question/Conflict:** What may the authenticated-user response expose?
- **Decision:** Return id, name, email, role, status, `must_change_password`, created_at, last_login_at. Never password/refresh/reset hashes or session secrets.
- **Why:** Role/status are safe UI metadata; the Back Office needs them to show admin nav and enforce first-login change. Hiding an admin link is **not** a substitute for backend enforcement.
- **Advantages:** UX without leaking secrets; backend remains the boundary.
- **Tradeoffs:** —
- **Phase owner:** Auth 1 (contract), Auth 2 (consumer).
- **Deferred:** —
- **Supports SQL migration:** `UserPublic` schema is persistence-agnostic.

### D9 — Protect domain services in Auth 1
- **Question/Conflict:** Defer Supplier Directory / Incident Processor protection to a later phase?
- **Decision:** No — Auth 1 plans token validation + rejection of unauthenticated requests for both, with a route-classification table across all three services.
- **Why:** Protecting only the frontend leaves the APIs publicly callable; an attacker could bypass `/login` and call `/suppliers` or incident endpoints directly.
- **Advantages:** The backend is the real boundary from day one.
- **Tradeoffs:** More Auth 1 scope; frontend may temporarily break against protected endpoints until Auth 2 (expected, per Auth 1 requirements).
- **Phase owner:** Auth 1.
- **Deferred:** —
- **Supports SQL migration:** Verification uses the public key, independent of persistence.

### D10 — Asymmetric JWT signing (RS256)
- **Question/Conflict:** Share one signing secret with every service?
- **Decision:** RS256. Identity service holds the **private** key and signs; domain services receive only the **public** key / JWKS and validate. Env: `IDENTITY_JWT_PRIVATE_KEY` (identity only), `IDENTITY_JWT_PUBLIC_KEY` (all verifiers), `IDENTITY_JWT_ALGORITHM=RS256`.
- **Why:** A shared symmetric secret means any service (if compromised) can mint valid tokens.
- **Advantages:** Only identity can issue tokens; least privilege; safer key distribution.
- **Tradeoffs:** Key generation/rotation procedure to document.
- **Phase owner:** Auth 1.
- **Deferred:** Automated key rotation tooling (document the manual procedure now).
- **Supports SQL migration:** Unrelated to persistence; unchanged by the SQL move.

### D11 — Add `name` and `must_change_password` to the user model
- **Question/Conflict:** Minimum model lacks `name` (Auth 2 needs it) and a forced-change flag.
- **Decision:** User model = `id, email, hashed_password, name, role, status, must_change_password, created_at, last_login_at`.
- **Why:** Profile editing (Auth 2) needs `name`; the temp-password flow (D13) needs `must_change_password`.
- **Advantages:** One coherent model across phases.
- **Tradeoffs:** —
- **Phase owner:** Auth 1.
- **Deferred:** —
- **Supports SQL migration:** Maps directly to a `users` table.

### D12 — Soft-disable for `DELETE /users/{id}`
- **Question/Conflict:** Hard delete or disable?
- **Decision:** `DELETE /users/{id}` sets `status=disabled` (reversible). Admin UI uses Suspend / Disable / Reactivate language.
- **Why:** Reversible, preserves historical references, avoids accidental data loss, safer for the future SQL move.
- **Advantages:** No dangling references; auditable.
- **Tradeoffs:** True deletion is a separate, later, controlled workflow.
- **Phase owner:** Auth 1 (endpoint), Auth 2 (UI).
- **Deferred:** Permanent-deletion workflow (legal/retention).
- **Supports SQL migration:** Status change avoids cascading-delete design now.

### D13 — Temporary initial password
- **Question/Conflict:** How does an admin-created user get a first password without email infra?
- **Decision:** `POST /users` generates a strong temp password, returns it **once**, stores only its Argon2id hash, sets `must_change_password=true`; admin never chooses/sees the permanent password; temp password never logged/redisplayed. While `must_change_password=true`, the backend restricts the user to viewing auth state, changing password, and logging out.
- **Why:** Enables admin-controlled creation without pulling Auth 3 email forward; forces rotation off the temporary credential.
- **Advantages:** No email dependency in Auth 1; least-privilege until rotated.
- **Tradeoffs:** Admin must hand off the password out-of-band.
- **Phase owner:** Auth 1 (backend), Auth 2 (UI display + first-login redirect).
- **Implemented after Auth 3:** Email invite / set-password link using the Auth 3 reset-token infrastructure. Temporary passwords are still returned once to admins as a fallback, but they are never emailed.
- **Supports SQL migration:** `must_change_password` is one boolean column.

### D14 — Environment-specific cookies + Production Deployment Gate
- **Question/Conflict:** Cookies can't be `Secure` on local HTTP, but must be in production.
- **Decision:** Dev (`http://localhost`): `HttpOnly=true`, `Secure=false`, `SameSite=Lax`, `Path=/`, no `Domain`. Prod: `HttpOnly=true`, `Secure=true`, `SameSite=Lax`, `Path=/`, no `Domain`, HTTPS required, host-only (prefer `__Host-` prefix where compatible). The **Production Authentication Deployment Checklist** (below) is a required deployment gate embedded in Auth 1 & Auth 2.
- **Why:** Local HTTP needs the dev exception; production must send auth cookies only over HTTPS. The gate prevents dev settings reaching production.
- **Advantages:** Secure prod defaults; smooth local dev.
- **Tradeoffs:** Environment-conditional config.
- **Phase owner:** Auth 1 + Auth 2 (and Auth 3 reset links use prod HTTPS URL).
- **Deferred:** —
- **Supports SQL migration:** Independent of persistence.

### D15 — BFF / same-origin proxy
- **Question/Conflict:** With cookie auth, how does the Next.js app talk to a separate identity service?
- **Decision:** Next.js BFF / same-origin proxy in `uis/backoffice` — route handlers under `app/api/{auth,users,suppliers,incidents}/*` forward to the services; the browser only talks to the Back Office origin. Cross-origin `SameSite=None` cookies considered and rejected.
- **Why:** Simpler same-origin cookies, fewer CORS issues, clearer CSRF, one FE API origin, hides internal service URLs, easier Next route protection.
- **Advantages:** Cleaner production routing model.
- **Tradeoffs:** Added proxy layer + deployment routing (accepted).
- **Phase owner:** Auth 2.
- **Deferred:** —
- **Supports SQL migration:** Frontend is unaffected by the backend persistence change.

### D16 — Suspension behavior + accepted 15-minute window
- **Question/Conflict:** Locally-validated JWTs can't be revoked mid-lifetime.
- **Decision:** On suspend/disable: revoke all refresh sessions immediately; reject future login + refresh; issue no new access tokens. An already-issued access token may remain valid up to its remaining ≤15-minute lifetime — accepted and documented for the TinyDB phase. **No** token introspection, shared denylist, or distributed revocation added now.
- **Why:** The short access-token lifetime bounds exposure while avoiding distributed infrastructure during the temporary TinyDB stage.
- **Advantages:** Simplicity; no cross-service revocation infra.
- **Tradeoffs:** Up to 15 minutes of residual access after suspension.
- **Phase owner:** Auth 1.
- **Deferred:** Token introspection / denylist (separate approval).
- **Supports SQL migration:** A future SQL session store could add introspection without API changes.

### D17 — Password-reset infra confined to Auth 3
- **Question/Conflict:** Build reset persistence/email in Auth 1?
- **Decision:** No. `PasswordResetRepository`, `password_resets` collection, email module, and reset endpoints/pages are built **only in Auth 3**. Reset tokens are random opaque values stored **hashed**, single-use, 15–60 min, scoped to reset; successful reset revokes all sessions; provider = **Resend**.
- **Why:** Preserves approval gates, avoids unfinished code, keeps each phase independently reviewable.
- **Advantages:** Clean phase boundaries.
- **Tradeoffs:** —
- **Phase owner:** Auth 3.
- **Deferred:** Rate limiting, audit logging, HTML email template (optional unless a repo-specific need is approved).
- **Supports SQL migration:** Reset records sit behind a repository interface like users/sessions.

### Auth 3 implementation notes — forgot password and onboarding

These notes capture the decisions made during Auth 3 implementation and local testing so the operational behavior is easy to revisit later.

#### Forgot password / account recovery

- `POST /auth/forgot-password` is public and accepts only `{ "email": string }`.
- The public response is always the same for valid input: `{"message":"If that address is registered, you'll receive a link shortly."}`. This applies whether the account exists, does not exist, is inactive, or email delivery fails.
- Only active registered users receive reset emails. Suspended, disabled, missing, and malformed accounts do not produce an email, but valid requests still get the generic public response.
- Reset tokens are opaque random values generated with `secrets.token_urlsafe(48)`. The raw token is sent only inside the reset link and is never stored.
- TinyDB stores reset records in `password_resets` with `id`, `user_id`, `token_hash`, `expires_at`, `used`, `created_at`, and `purpose`.
- `token_hash` is a SHA-256 digest of the raw token. Tokens, hashes, reset URLs, passwords, API keys, and email addresses must not be logged.
- Reset tokens are single-use and time-limited. Local default is `RESET_TOKEN_EXPIRE_MINUTES=30`; valid configuration must stay within the approved 15-60 minute window.
- Issuing a new reset token invalidates prior unused reset tokens for that user.
- `POST /auth/reset-password` accepts `{ "token": string, "new_password": string }`.
- Invalid, expired, used, wrong-purpose, or invalid-account reset tokens return a generic `400` error.
- A successful reset writes a new Argon2id password hash, clears `must_change_password`, marks the token used, invalidates remaining reset tokens for the user, and revokes all refresh sessions.
- Resend is the email provider for this phase. Email configuration must come only from environment variables: `RESEND_API_KEY`, `EMAIL_SENDER`, `FRONTEND_BASE_URL`, and `RESET_TOKEN_EXPIRE_MINUTES`.
- Reset links are built from `FRONTEND_BASE_URL` as `/reset-password?token=<encoded-token>`. Local development uses `http://localhost:3000`; production must use the HTTPS Back Office origin.
- Email provider failures are caught inside the forgot-password flow. The user still sees the same generic response, and logs contain only a redacted event with user id and error type.

#### Admin-created user onboarding

- Public registration remains intentionally unavailable. `/auth/register` does not exist. Admin-only `POST /users` is still the only user-creation path.
- Admin-created users are created as `role="user"`, `status="active"`, and `must_change_password=true`.
- The backend generates a strong one-time temporary password and stores only its Argon2id hash.
- The temporary password is returned once to the admin as a fallback. It is never redisplayed and must never be logged.
- After Auth 3 email infrastructure existed, onboarding was updated to send a safer account setup email instead of relying only on manual temp-password handoff.
- The setup email uses the same reset-token infrastructure as forgot password, but the token purpose is `account_setup`.
- Account setup emails contain a one-time `/reset-password?token=...` link that lets the new user choose their own password.
- The raw temporary password is never emailed. This follows the authentication security rule: reset/setup flows use single-use, time-limited out-of-band tokens and never email passwords.
- If account setup email delivery succeeds, the Back Office shows "Setup email sent..." and still displays the temporary password once as a fallback.
- If account setup email delivery fails, the account is still created, the Back Office shows "Setup email could not be sent automatically...", and the admin can securely deliver the one-time temporary password.
- A user who follows the setup email link and chooses a password has `must_change_password=false` after reset.
- A user who signs in with the fallback temporary password is routed into the first-login password change flow and remains restricted until the password is changed.
- Local testing revealed an important Resend limitation: `EMAIL_SENDER=onboarding@resend.dev` can only send testing emails to the Resend account owner's allowed email address. Sending setup emails to arbitrary recipients, including Gmail addresses, requires verifying a domain in Resend and using a sender address on that verified domain.

---

## 7. Decisions Still Requiring Approval

These are recorded rather than guessed; defaults are noted but should be confirmed before/at implementation:

- Exact key-rotation procedure and cadence for `IDENTITY_JWT_PRIVATE_KEY`/`PUBLIC_KEY` (default: documented manual rotation).
- Whether to add rate limiting/lockout on `/auth/login` and (Auth 3) `/auth/forgot-password` in-phase or defer (default: defer, optional).
- Whether to add audit logging of auth events now or defer (default: defer, optional).
- Production hosting topology (single host for Back Office + `/api/*` is assumed by D15; confirm).
- Max active sessions per user / "log out everywhere" UI (default: not in scope).
- Whether sensitive actions beyond password change require step-up reauth (default: none beyond password change).
- True user deletion workflow and data-retention policy (default: deferred; soft-disable only).

### Production Authentication Deployment Checklist (required deployment gate)

`Secure=false` is allowed **only** for local development over `http://localhost`. When hosted, `Secure=true` and HTTPS are **required**. Before any production deployment of authenticated TrackFlow:

- [ ] HTTPS enabled for the production Back Office.
- [ ] Authentication cookies set to `Secure=true`.
- [ ] `HttpOnly=true` kept.
- [ ] Approved `SameSite=Lax` kept.
- [ ] No broad cookie `Domain` (host-only; `__Host-` prefix where compatible).
- [ ] Correct production frontend and service URLs configured.
- [ ] Development secrets and signing keys replaced with production secrets.
- [ ] Secrets stored only in deployment environment variables — never committed.
- [ ] Reverse proxy configured so the apps correctly recognize HTTPS (forwarded-proto).
- [ ] Trusted origins / CORS configured without wildcard origins paired with credentials.
- [ ] (Auth 3) Password-reset links use the production HTTPS Back Office URL.
- [ ] Post-deployment test of login, refresh, logout, CSRF, protected routes, and cookie behavior.

---

## 8. Change History

| Date | Change | Decisions affected |
|---|---|---|
| 2026-06-20 | Added implementation notes for forgot-password/account-recovery behavior and admin-created user onboarding setup emails. | D4, D13, D17 |
| 2026-06-19 | Initial decision record created from planning handoff and four rounds of user direction. | D1–D17, deployment gate |
