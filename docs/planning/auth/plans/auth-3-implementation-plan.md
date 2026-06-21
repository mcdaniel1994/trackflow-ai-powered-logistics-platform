# Auth 3 — Implementation Plan: Password Reset + Account Recovery

**Status:** Implemented and locally verified on 2026-06-20. **Phase:** 3 of 3. **Requirements:** `docs/planning/auth/auth-3-password-reset-requirements.md`. **Decisions:** `docs/planning/auth/auth-security-decisions.md`. **Standard:** `docs/standards/authentication-security-rule.md`.

> **Phase gate:** Auth 3 must not begin until Auth 1 and Auth 2 are implemented, tested, reviewed, and approved. All password-reset persistence, email, endpoints, and pages live **only** in this phase.

---

## 1. Objective and Scope

Add account recovery for users who have forgotten their password: backend forgot-password / reset-password endpoints, secure single-use reset tokens, transactional email (Resend), and the frontend `/forgot-password` and `/reset-password` pages plus the `/login` recovery link. Account-enumeration protection throughout.

**In scope:** `POST /auth/forgot-password`, `POST /auth/reset-password`; `password_resets` TinyDB collection + `PasswordResetRepository`; email module (Resend) with safe failure handling; `/forgot-password` + `/reset-password` pages (public) via the BFF; "Forgot your password?" link on `/login`; tests; env/config docs.

**Out of scope (optional unless approved):** rate limiting, audit logging, styled HTML email template; any broad email-platform build; changes to Auth 1/2 contracts beyond reusing them.

---

## 2. Relevant Repository Findings (exact paths)

- Identity service (from Auth 1): `services/identity/identity/` — `security.py` (Argon2id + token helpers to reuse), `repository.py` (interfaces + TinyDB impls to extend), `service.py` (`AuthService` — add reset flows), `main.py` (`/auth` router), `config.py`, `.env.example`.
- Hashing to reuse: Argon2id from Auth 1 `security.py`. Session revocation to reuse: `AuthService.revoke_all_for_user` (Auth 1).
- Frontend (from Auth 2): `uis/backoffice/app/login/page.tsx`, BFF handlers `uis/backoffice/app/api/auth/[...path]/route.ts`, auth lib `uis/backoffice/lib/auth/*`, UI primitives `uis/backoffice/components/talent/ui/*`.
- No email integration exists anywhere in the repo (greenfield).

---

## 3. Proposed Design

### Reset token (random, hashed, single-use)
- **Cryptographically random opaque token** (e.g. `secrets.token_urlsafe`), **not** a JWT — server state is required to enforce one-time use and revocation. Never reuse or derive from the access token; the reset token can never act as an access token and vice-versa.
- Stored **only as a hash** in `password_resets` with `user_id`, `token_hash`, `expires_at` (configurable 15–60 min, default 30), `used` (bool), `created_at`.
- Single-use: marked `used=true` atomically on successful reset; reuse → 400. Expiry → 400. Wrong/unknown/inactive account → 400. Generic error detail (no internal token-validation specifics).
- **Successful reset revokes all active refresh sessions** for the user (reuse Auth 1 revocation).

### Enumeration protection
`POST /auth/forgot-password` always returns `200 OK` with the same body for any syntactically valid email, whether or not it is registered/active, and whether or not email delivery succeeded. Suggested message: *"If that address is registered, you'll receive a link shortly."* Provider failures are caught, logged safely (no token, no PII, no secrets), and never alter the response.

### Email
- **Provider: Resend** (simpler dev onboarding; single API key; good DX). Behind an `EmailSender` abstraction in the identity service so it is mockable in tests and swappable later.
- Reset link uses an **env-configured frontend origin** (`FRONTEND_BASE_URL`), never a hardcoded host: `{FRONTEND_BASE_URL}/reset-password?token=<token>`. Token URL-encoded; never logged.
- Email content: explains a reset was requested, the reset link, the expiration window, and guidance to ignore if not requested. Mobile-readable. Plain text required; styled HTML optional (see §12 optional).

---

## 4. Files to Create

Identity service (`services/identity/identity/`):
- `email.py` — `EmailSender` interface + `ResendEmailSender`; safe error handling; no key in code.
- `reset_models.py` (or extend `models.py`) — `ForgotPasswordRequest {email}`, `ResetPasswordRequest {token, new_password}`.
- Tests: `identity/tests/test_password_reset.py`, `identity/tests/test_email.py`.

Frontend (`uis/backoffice/`):
- `app/forgot-password/page.tsx` — public; email input, pending, confirmation; disables form after submit; identical message regardless of account existence.
- `app/reset-password/page.tsx` — public; reads `token` from query, validates presence, matches new-password + confirm, submits, redirects to `/login` on success, shows clear error on invalid/expired with a link back to `/forgot-password`.
- `components/auth/ForgotPasswordForm.tsx`, `components/auth/ResetPasswordForm.tsx` (reuse `components/talent/ui/*`).

---

## 5. Files to Modify

Identity service:
- `repository.py` — add `PasswordResetRepository` interface + `TinyDBPasswordResetRepository`; methods: create, get-by-token-hash, mark-used, revoke-for-user, cleanup-expired.
- `service.py` — `AuthService.request_password_reset(email)` (find active user, create reset record, send email; always succeed publicly) and `reset_password(token, new_password)` (validate hash/expiry/used → set Argon2id hash → mark used → revoke all sessions).
- `main.py` — add `POST /auth/forgot-password` (public) and `POST /auth/reset-password` (public) to the `/auth` router.
- `config.py` + `.env.example` — add the email/reset env vars (§9).
- `pyproject.toml` — add the Resend client dependency.

Frontend:
- `app/login/page.tsx` (or `components/auth/LoginForm.tsx`) — add a visible **"Forgot your password?"** link to `/forgot-password`.
- `app/api/auth/[...path]/route.ts` — ensure `forgot-password` and `reset-password` are forwarded (public; no session required).
- Route protection config (Auth 2 `middleware.ts` / `(protected)` layout) — ensure `/forgot-password` and `/reset-password` are in the **open** set.
- `README.md` (backoffice + identity) — document the reset flow and the production reset-URL gate.

---

## 6. Database / Persistence Changes (TinyDB)

New collection `password_resets` in the identity TinyDB (same DB file as `users`/`refresh_sessions`):
- `id`, `user_id`, `token_hash`, `expires_at` (UTC ISO), `used` (bool), `created_at` (UTC ISO).

Safeguards (consistent with Auth 1): store only token **hashes**; UTC timestamps; atomic mark-used; single-worker concurrency caveat documented; cleanup of expired/used records. Behind the `PasswordResetRepository` interface for the deferred SQL migration.

---

## 7. API Changes

- `POST /auth/forgot-password` — body `{email}`; always `200 OK` with the generic message for any valid request; no enumeration; provider failures logged safely without changing the response.
- `POST /auth/reset-password` — body `{token, new_password}`; validate token hash/purpose/expiry/used + active account; on success set Argon2id hash, mark token used, revoke all sessions, `200`; on any failure `400 Bad Request` with a generic detail.

Both are **Public** in the route-classification table. Access tokens cannot be used as reset tokens and reset tokens cannot be used as access tokens (separate secrets/formats/stores).

---

## 8. Frontend Changes

- `/forgot-password` (public): email + submit + pending + confirmation; form disabled after submit to prevent duplicates; never reveals registration status.
- `/reset-password` (public): reads `token` from the query string; requires token present before submit; confirms passwords match; calls `POST /api/auth/reset-password`; on success redirect to `/login` with a success indicator via the approved mechanism; on invalid/expired shows a clear error and a link to `/forgot-password`. Never treats decoded token contents as trusted identity.
- `/login`: visible "Forgot your password?" link → `/forgot-password`.

---

## 9. Environment Configuration

Identity `.env.example` additions (placeholders only):

```
RESEND_API_KEY=                  # transactional email key (never commit)
EMAIL_SENDER=no-reply@trackflow.example
FRONTEND_BASE_URL=http://localhost:3000   # production: the HTTPS Back Office URL
RESET_TOKEN_EXPIRE_MINUTES=30    # configurable 15–60
```

Reset links must use the production HTTPS Back Office URL in production (deployment gate, below). No email key or token value is ever hardcoded or logged.

---

## 10. Dependencies (documented; install only at implementation time)

Identity service: the Resend Python client (`resend`). Dev/test: existing `pytest`/`httpx`; email is mocked in tests (no live sends).

---

## 11. Testing Plan

Reuse the Auth 1 pytest + `TestClient` pattern with an isolated TinyDB and a mocked `EmailSender`. Cover (Auth 3 requirements §13 + standard §17):
- Forgot-password with a registered email vs an unregistered email → **identical** public `200` responses.
- Email send invoked for a registered/active user; mocked-delivery boundary; provider failure does not change the public response and logs no secrets.
- Reset-token creation; purpose/scope; expiration; invalid token; expired token → 400.
- Successful reset: password re-hashed (Argon2id); old password no longer works; new password logs in.
- **Single-use:** reusing an already-used token → 400; reset revokes all active sessions.
- Reset page: missing token blocks submit; mismatched confirmation blocked; invalid-token error path with link back to `/forgot-password`.
- Successful frontend reset flow → redirect to `/login`.
- Login-page recovery link present and navigates to `/forgot-password`.
- Env-variable loading; no API key or token value appears in committed code or logs (assert redaction / absence).

Frontend tests use the Auth 2 Vitest + RTL + Playwright setup.

---

## 12. Manual Verification

1. Open `/forgot-password`; submit a registered email → generic confirmation; form disabled.
2. Confirm a reset email is delivered (dev: Resend test mode / mailbox).
3. Open the reset link → token read from URL.
4. Submit matching new-password fields → redirect to `/login`.
5. Log in with the new password → succeeds; old password rejected.
6. Reuse the same reset link → 400 invalid/expired message.
7. Submit `/forgot-password` for an unregistered email → identical generic confirmation.
8. Test an expired token → API returns 400; frontend offers a link back to `/forgot-password`.
9. Confirm no API key or reset-token value appears in committed code or unsafe logs.

### Optional (only if a repo-specific need is approved)
- Styled HTML email template (alongside required plain text).
- Rate limiting on `/auth/forgot-password` (by email-derived id / IP / window) — public response stays identical.
- Audit logging of reset requested/completed/failed (never logging token/password values).

---

## 13. Acceptance Criteria

- `POST /auth/forgot-password` exists and always returns a non-enumerating `200` for valid requests.
- Registered users receive a real reset email with a functional link; reset tokens expire within the configured 15–60 min window.
- Reset tokens are random, stored hashed, single-use; already-used and invalid/expired tokens → `400`.
- Passwords hashed (Argon2id) before storage; successful reset revokes all active sessions.
- `/forgot-password` shows the generic confirmation; `/reset-password` reads the query token, redirects to `/login` on success, and shows a clear recovery path on failure.
- `/login` has a visible forgot-password link.
- Email-provider secrets come only from env; nothing committed/logged.
- Access tokens cannot be used as reset tokens and vice-versa.
- Required tests pass; Auth 1 and Auth 2 remain intact.
- **Production Authentication Deployment Checklist** satisfied (reset links use the production HTTPS URL).

### Production Authentication Deployment Checklist (deployment gate — reset specifics)
- [ ] `FRONTEND_BASE_URL` set to the production HTTPS Back Office URL so reset links are HTTPS.
- [ ] `RESEND_API_KEY`/`EMAIL_SENDER` from deployment env only (not committed).
- [ ] Cookie/HTTPS items per the Auth 1/2 gate remain satisfied.
- [ ] Post-deploy test of the full reset flow over HTTPS.

---

## 14. Implementation Checklist

- [x] Add `EmailSender` + `ResendEmailSender` (`email.py`).
- [x] Add `PasswordResetRepository` interface + TinyDB impl; `password_resets` collection.
- [x] `AuthService.request_password_reset` + `reset_password` (reuse Argon2id + revoke-all-sessions).
- [x] Add `POST /auth/forgot-password` + `POST /auth/reset-password` (public).
- [x] Identity `config.py`/`.env.example`/`pyproject.toml` updates.
- [x] Frontend `/forgot-password`, `/reset-password`, `/login` link; BFF forwarding; open-route config.
- [x] Tests per §11; local verification per §12 using mocked email delivery.
- [x] Update engagement-tracking docs per AGENTS.md pre-commit workflow.

---

## 15. Decisions Requiring Approval (carried from the decision record)

- Exact `RESET_TOKEN_EXPIRE_MINUTES` within 15–60 (default 30).
- Whether rate limiting and/or audit logging are added now or remain optional (default: optional/deferred).
- Whether to ship the styled HTML email template now or plain text only (default: plain text required, HTML optional).
- Sender identity/domain verification approach in Resend for production.

---

## 16. Approval Gate

Auth 3 is the final phase. Begin only after Auth 1 and Auth 2 are implemented, tested, reviewed, and approved. Optional extensions (§12) stay clearly separated from required work and need their own approval.
