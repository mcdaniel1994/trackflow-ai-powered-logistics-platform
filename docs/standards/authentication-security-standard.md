# Authentication & Session Security Standard

**Last reviewed:** June 2026  
**Next review due:** September 2026 (quarterly)

## 1. Scope

Applies to web apps (Python/FastAPI + SQL + JS frontends) and AI-driven applications.

## 2. Purpose
A reusable operating standard for implementing, modifying, and reviewing authentication. It sets secure defaults, names tradeoffs, and marks each choice as **recommended**, **acceptable for prototypes**, or **unsafe for production**. It is the bar to clear before auth code ships — not a tutorial.

## 3. When To Use This Standard
Apply this standard to any change touching login/logout, registration, password reset, sessions, tokens, cookies, CORS/CSRF/XSS surface, middleware, route protection, role/permission checks, or any flow where an AI agent acts for a user. If a change can affect *who is authenticated* or *what they can reach*, this standard applies.

## 4. Core Security Rules
- **The backend is the only real security boundary.** The frontend is attacker-controlled. Never trust client-supplied identity, roles, or flags.
- **Authentication ≠ authorization.** Authentication proves *who* the user is; authorization decides *what* they may do. Passing one never grants the other.
- **The SQL database is the source of truth** for users, roles, permissions, active sessions, revoked tokens, and tenant boundaries.
- **Decide security per request, server-side.** Every protected action is re-verified against the database.
- **Least privilege, deny by default.** New endpoints are protected until explicitly opened.

## 5. Secure Defaults
Default to these unless a documented reason overrides them:
- Hash passwords with **Argon2id**.
- **HTTPS/TLS only.**
- Browser auth via **`HttpOnly; Secure; SameSite` cookies**; never `localStorage`/`sessionStorage`.
- **Short-lived access tokens (5–15 min)** + **rotating refresh tokens** backed by a server-side revocation store.
- Authorization checked on **every** request via a server dependency.
- Generic auth-failure messages ("invalid email or password") to prevent user enumeration.
- Sensitive operations (password/email change, payments) require **re-authentication** or step-up.
- Secrets from environment/secret manager — never hardcoded or committed.

## 6. Authentication Flow Recommendations
**Recommended (solo/small-team production):** token-in-cookie or server-side session. On login, verify credentials, create a server-side session/refresh record, and set a short access token + rotating refresh token in `HttpOnly` cookies. JavaScript never touches them.

**Acceptable for prototypes/learning:** access token in JS memory (a variable, not storage) with the refresh token in an `HttpOnly` cookie. Tokens clear on reload — a usability cost that limits exposure.

**Unsafe for production:** tokens in `localStorage`/`sessionStorage` (any XSS on the origin reads them); long-lived access tokens; refresh tokens without rotation/revocation; trusting client-issued tokens. **Long-lived JWTs are acceptable only in isolated local learning demos and must never be used in production.**

**OAuth 2.0 / OIDC:** follow RFC 9700. Use the **authorization code flow with PKCE for all clients**, exact-match redirect URIs, the `state` parameter, one-time-use authorization codes, and refresh token rotation. Prefer a managed identity provider over hand-rolled OAuth.

## 7. Token and Session Handling Rules
- **Verify every token, every request:** signature, expiration (`exp`), issuer (`iss`), audience (`aud`), and algorithm. Reject `alg: none` for signed authentication tokens and never honor a client-chosen algorithm. Follow RFC 8725 for JWT implementation security and RFC 7519 for JWT structure.
- **Access tokens stay short-lived** — they are bearer credentials; whoever holds one can use it until expiry.
- **Refresh tokens rotate:** issue a new one on each use and invalidate the old. If a rotated-out refresh token is presented, **treat it as theft — revoke the entire token family/session** and force re-auth (RFC 9700).
- **Revocation is server-side.** Keep sessions/refresh tokens in SQL so logout, password change, and admin action invalidate them immediately. Pure stateless JWTs can't be revoked before expiry — accept that only with very short lifetimes.
- **Store refresh tokens hashed at rest** (treat them like passwords).
- **Never put sensitive data or secrets in a JWT payload** — it is Base64, readable by anyone. Carry only a user ID and minimal claims; keep PII, detailed permissions, and secrets in the database.
- For higher assurance, consider sender-constrained tokens (DPoP/mTLS) per RFC 9700.

## 8. Password Handling Rules
Use a **slow, memory-hard, salted** algorithm (OWASP Password Storage Cheat Sheet):
- **Argon2id** — ≥19 MiB memory, iterations=2, parallelism=1 (or 46 MiB / 1 / 1). Preferred.
- **scrypt** — N=2¹⁷, r=8, p=1, if Argon2id is unavailable.
- **bcrypt** — work factor ≥12; pre-hash inputs over its 72-byte limit. Acceptable for legacy.
- **PBKDF2-HMAC-SHA256** — ≥600,000 iterations, only when FIPS forces it.

Rules: never use fast hashes (MD5/SHA-1/SHA-256) or encryption for passwords; let the library handle salting (don't roll your own); verify in constant time; re-hash on login when parameters rise. Follow NIST SP 800-63B: 8+ chars, allow long passphrases, screen against breached-password lists, no forced periodic resets. Reset flows use single-use, time-limited, random tokens out-of-band — never email the password.

## 9. Cookie, CSRF, and XSS Rules
**Cookies** — set auth cookies with: `HttpOnly` (blocks JS access), `Secure` (HTTPS only), `SameSite=Strict` (or `Lax` if cross-site top-level navigation must stay logged in; `None` only when genuinely cross-site, always with `Secure`), scoped `Path`, the `__Host-` prefix where possible, and `Max-Age` ≤ token lifetime.

**XSS** — `HttpOnly` cookies **reduce token-theft risk but do not eliminate it; XSS prevention is still required.** Set a strict **Content-Security-Policy**; escape/encode all user-rendered output; rely on framework auto-escaping; avoid `innerHTML`/`dangerouslySetInnerHTML` with untrusted data; keep dependencies patched (XSS often enters via third-party scripts). Treat `HttpOnly` cookies and XSS prevention as layered defenses, not alternatives (OWASP XSS Prevention Cheat Sheet).

**CSRF** — for cookie-based auth, protect state-changing requests (POST/PUT/PATCH/DELETE) with a **CSRF token** (synchronizer or double-submit pattern), verified server-side. `SameSite` and CORS reduce exposure but **are not, on their own, CSRF protection** (OWASP CSRF Prevention Cheat Sheet). Header-based bearer tokens aren't CSRF-prone (the browser won't auto-attach the header) but are exposed to XSS — choose the threat you defend against deliberately.

## 10. Middleware Security Rules
Middleware is for **cross-cutting request protections**, not the security decision itself. It runs broadly and early; it does not know per-resource context.

**Appropriate in middleware:**
- **CORS** enforcement with an explicit allowlist of trusted origins (never `*` paired with credentials).
- **Security headers** — CSP, HSTS, `X-Content-Type-Options: nosniff`, frame/referrer policy.
- **Safe request logging** with sensitive headers (`Authorization`, `Cookie`) redacted.
- **Rate limiting / lockout** on login, registration, password reset, and token refresh endpoints.
- **CSRF validation** for cookie-authenticated, state-changing requests.
- **Request correlation IDs** for auditability and debugging.
- **Optional session/token parsing** that attaches *safe* request context (e.g., a user ID), without becoming the authorization check.

**Still enforced by route dependencies and backend services — never delegated to middleware alone:**
- The user is authenticated.
- The account is active.
- The session or token has not been revoked.
- The user has the required role or permission.
- The user owns, or is allowed to access, the specific resource.
- Tenant, organization, or workspace boundaries hold.

> **Principle:** Middleware handles broad request protections. Route dependencies and backend services enforce the actual security decision.

## 11. Backend Authorization Rules
- Enforce authorization **server-side on every protected endpoint**, even when the UI already hides the option.
- Check **ownership and scope**, not just authentication: a logged-in user must not reach another user's records by changing an ID (no IDOR). Filter every query by the authenticated principal.
- **Enforce tenant/organization/workspace boundaries** on every query and mutation in multi-tenant apps.
- Keep roles/permissions in SQL and resolve them per request; never accept a role from the client.
- Re-check authorization after any privilege-relevant state change (OWASP Authorization Cheat Sheet, API Security Top 10).

## 12. FastAPI / SQL Implementation Guidance
- Use dependency injection for auth: a `get_current_user` dependency extracts the credential (cookie or `OAuth2PasswordBearer`), verifies it, loads the user from SQL, and raises `HTTPException(401)` on failure; layer `get_current_active_user` and `require_role(...)`/scope dependencies for authorization. Resolve identity **once** in a dependency and inject the validated user — don't re-parse tokens in handlers.
- Use parameterized queries / an ORM (SQLAlchemy) exclusively — never string-format SQL.
- Tables: `users` (id, email, `password_hash`, status); `sessions`/`refresh_tokens` (hashed token, user_id, expiry, revoked flag, family id); `roles`/`permissions`; tenant/org IDs on owned resources.
- Use `argon2-cffi`/`passlib` for hashing and `pyjwt`/`python-jose` with full claim verification; load signing keys from the environment.
- Set cookies via the response with the flags in §9. Configure **CORS narrowly** (explicit origins; `allow_credentials=True` only with a specific origin list).
- Keep route-level checks even when middleware exists (see §10).

## 13. Logging and Debugging Rules
- **Never log** passwords, password hashes, raw tokens, refresh tokens, session cookies, `Authorization` headers, secrets, or full sensitive records. Redact before any log call.
- **Do log auth events** — login success/failure, logout, token rotation, refresh-reuse detection, permission denials, role changes — with user ID, timestamp, and correlation ID, not the credentials.
- Keep tokens/secrets out of error responses, stack traces, URLs/query strings, and analytics.
- Disable verbose error output in production; return generic client messages, log detail server-side.

## 14. AI-Agent Safety Rules
- **Resolve auth before the agent acts.** The backend authenticates the user and computes permissions first; the agent runs inside that decided context.
- Give the agent only **sanitized, permissioned, task-specific** context — never raw JWTs, cookies, credentials, refresh tokens, or whole user/DB records.
- **Agent tool calls are constrained by backend-validated identity and permissions.** Each tool re-checks authorization server-side; never let the model self-assert who it is or what it may do.
- **No secrets in prompts, traces, debug output, tool results, or frontend state** (governed by §13).
- Apply least privilege to tool scopes; log sensitive agent actions safely (the event, not the data).
- Treat model/prompt content as untrusted input: it must never widen authorization or override server policy (OWASP Top 10 for LLM Applications).

## 15. What To Avoid
- Tokens/credentials in `localStorage`/`sessionStorage`.
- Trusting client-supplied roles, IDs, or auth flags.
- Long-lived access tokens; refresh tokens without rotation/revocation; long-lived JWTs in production.
- Sensitive data or secrets in JWT payloads.
- Fast hashes or encryption for passwords; home-grown crypto.
- Authorization done only in the frontend, only in middleware, or only at login time.
- Treating `SameSite`/CORS as sufficient CSRF protection; `CORS *` with credentials.
- Logging or echoing secrets, tokens, cookies, or full records.
- Feeding raw credentials/tokens to AI agents.
- Disabling TLS, signature checks, or expiry validation "temporarily."

## 16. Review Checklist
- [ ] Passwords hashed with Argon2id (or approved fallback) at specified parameters.
- [ ] Tokens in `HttpOnly; Secure; SameSite` cookies; nothing in web storage.
- [ ] Access tokens short-lived; refresh tokens rotate; reuse revokes the family.
- [ ] Server-side session/revocation store enables instant logout.
- [ ] JWT signature, `exp`, `iss`, `aud`, and `alg` verified every request; `alg:none` rejected.
- [ ] No sensitive data/secrets in token payloads.
- [ ] AuthZ enforced server-side on every endpoint; ownership and tenant boundaries checked (no IDOR).
- [ ] CSRF protection on cookie-based state-changing requests.
- [ ] Middleware covers CORS, security headers, rate limiting, redacted logging, correlation IDs — without replacing route checks.
- [ ] CSP set; output escaped; deps audited.
- [ ] No secrets/tokens in logs, traces, errors, URLs, or prompts.
- [ ] AI agents get only sanitized, permissioned context; tools re-validate server-side.
- [ ] Secrets from env/secret manager; none committed.

## 17. Required Tests
- Unauthenticated request to a protected route → 401.
- Authenticated-but-unauthorized user (wrong role / not owner / wrong tenant) → 403; cannot reach another user's records by ID.
- Expired, tampered, wrong-`alg`, and wrong-`aud` tokens → rejected.
- Logout / password change immediately invalidates existing sessions and refresh tokens.
- Reused (rotated-out) refresh token → whole family revoked.
- Login failure returns a generic message (no enumeration); rate limit/lockout triggers.
- Cookies carry `HttpOnly`, `Secure`, `SameSite`.
- Password reset token is single-use and time-limited.
- Logs/traces/error responses contain no secrets, tokens, or full records (assert redaction).
- Agent context fixtures contain no raw credentials/tokens; agent tool denied when backend permission is absent.

## 18. Sources To Consult
- **OWASP Cheat Sheet Series** — Authentication; Session Management; Password Storage; CSRF Prevention; XSS Prevention; Authorization; JSON Web Token. <https://cheatsheetseries.owasp.org>
- **OWASP API Security Top 10** and **OWASP Top 10 for LLM Applications**. <https://owasp.org>
- **IETF RFC 7519** — JSON Web Token (JWT). <https://www.rfc-editor.org/info/rfc7519/>
- **IETF RFC 8725** — JSON Web Token Best Current Practices. <https://www.rfc-editor.org/info/rfc8725/>
- **IETF RFC 9700** — Best Current Practice for OAuth 2.0 Security (Jan 2025). <https://www.rfc-editor.org/info/rfc9700/>
- **FastAPI Security documentation** — OAuth2, JWT, dependencies, scopes. <https://fastapi.tiangolo.com/tutorial/security/>
- **MDN Web Docs** — `Set-Cookie`, `HttpOnly`, `Secure`, `SameSite`, CORS, CSP, security headers. <https://developer.mozilla.org>
- **NIST SP 800-63B-4** — Digital Identity Guidelines: Authentication and Authenticator Lifecycle.
