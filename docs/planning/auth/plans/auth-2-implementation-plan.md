# Auth 2 — Implementation Plan: Frontend Authentication Flows + Protected Views

**Status:** Planning (no code written). **Phase:** 2 of 3. **Requirements:** `docs/planning/auth/auth-2-frontend-requirements.md`. **Decisions:** `docs/planning/auth/auth-security-decisions.md`. **Standard:** `docs/standards/authentication-security-standard.md`.

> **Phase gate:** Auth 2 must not begin until Auth 1 is implemented, tested, reviewed, and approved. Password-reset pages/links are **not** in this phase (Auth 3).

---

## 1. Objective and Scope

Connect the existing `uis/backoffice` Next.js app to the Auth-1-secured backend via a **Next.js BFF / same-origin proxy**: login, admin-controlled user creation UI, authenticated state, authenticated API requests, protected views, profile + change-password, the temporary-password first-login flow, logout, and centralized `401` handling. The public site `uis/website` stays fully public and untouched.

**In scope:** `/login`, `/account/profile`, `/account/change-password`, `/admin/users`; BFF route handlers; auth context/provider; route protection; adapting existing `lib/*/api.ts` clients; cookie/CSRF handling via the BFF; test tooling (Vitest + RTL + Playwright); production deployment gate.

**Out of scope:** `/register` (does not exist — administrator-controlled creation only); forgot/reset-password pages and the `/login` recovery link (Auth 3); any change to `uis/website`'s access model; standalone auth app; backend changes beyond what Auth 1 delivered.

---

## 2. Relevant Repository Findings (exact paths)

- App: `uis/backoffice` — Next.js **16.2.6 App Router**, React 19, TS. `package.json` scripts: `dev/build/start/type-check/lint`. **No test framework installed.**
- Routes (App Router): `uis/backoffice/app/page.tsx` (`/` inventory+carriers), `app/incidents/page.tsx`, `app/suppliers/page.tsx` (+`new/`, `[id]/`), `app/talent/page.tsx` (+`new/`, `[id]/`).
- Root layout: `uis/backoffice/app/layout.tsx` (minimal `<html><body>`; **no auth provider**).
- Navigation: `uis/backoffice/components/BackofficeNavigation.tsx` (`"use client"`, `usePathname`).
- API clients (per-feature `fetch` wrappers, no central client): `uis/backoffice/lib/suppliers/api.ts` (default `http://localhost:8001`, `NEXT_PUBLIC_SUPPLIER_DIRECTORY_API_URL`, structured `parseAPIError` incl. FastAPI 422 `detail[]` → field errors), `uis/backoffice/lib/incident-api.ts` (`NEXT_PUBLIC_INCIDENT_PROCESSOR_API_URL`/`NEXT_PUBLIC_API_URL`, default `:8000`), `uis/backoffice/lib/talent/api.ts` (`NEXT_PUBLIC_TALENT_API_URL`).
- Public site: `uis/website` — separate Next.js app; hits no identity service; must remain fully public.
- Workspace: root `package.json` workspaces `["packages/*","uis/*"]`.

---

## 3. Proposed Design (BFF / same-origin)

The browser talks **only to the Back Office origin**. Next.js **route handlers** under `uis/backoffice/app/api/*` proxy to the backend services using **server-only** env vars. Auth cookies are same-origin, HttpOnly, host-only; CSRF uses double-submit.

```
Browser ──(same-origin, cookies)──> /api/auth/*       → identity service
                                     /api/users/*      → identity service
                                     /api/suppliers/*  → supplier-directory
                                     /api/incidents/*  → incident-processor
```

- **Considered & rejected:** cross-origin cookies (`SameSite=None; Secure`) directly from browser to each service — more CORS/CSRF surface, exposes internal URLs, harder Next route protection. Documented as alternative only.
- **Validity** is determined server-side via the identity `/auth/me` (session bootstrap), never by trusting decoded token contents in the browser.
- The BFF forwards the access cookie to identity for `/auth/me` and forwards/handles `Set-Cookie` from login/refresh back to the browser. On a backend `401`, the BFF surfaces `401` so the client clears state and redirects.

### Auth state
A client `AuthProvider` (React context) hydrated from a server-side session bootstrap (a server component or BFF endpoint calling `/auth/me`). Exposes `user` (`UserPublic` incl. `role`, `status`, `must_change_password`), `loading`, and `logout()`. `role` drives admin-nav visibility; `must_change_password` drives the first-login redirect. **The backend remains the security boundary** — hidden nav/guards are UX only.

---

## 4. Files to Create (under `uis/backoffice/`)

- BFF route handlers: `app/api/auth/[...path]/route.ts` (login, refresh, logout, me, change-password), `app/api/users/[...path]/route.ts`, `app/api/suppliers/[...path]/route.ts`, `app/api/incidents/[...path]/route.ts`. Forward method/body/cookies; attach CSRF; relay `Set-Cookie`; map errors.
- Auth core: `lib/auth/context.tsx` (`AuthProvider`, `useAuth`), `lib/auth/session.ts` (server-side `/auth/me` bootstrap), `lib/auth/api.ts` (login/logout/refresh/changePassword/me against `/api/auth/*`), `lib/auth/types.ts` (`AuthUser` = `UserPublic`), `lib/auth/csrf.ts`.
- Pages: `app/login/page.tsx`; `app/account/profile/page.tsx`; `app/account/change-password/page.tsx`; `app/admin/users/page.tsx` (+ `app/admin/users/new/page.tsx` or a modal).
- Protected layout: `app/(protected)/layout.tsx` (or middleware) guarding the authenticated app; keep `/login` outside it.
- Components: `components/auth/LoginForm.tsx`, `components/account/ProfileForm.tsx`, `components/account/ChangePasswordForm.tsx`, `components/admin/UserTable.tsx`, `components/admin/CreateUserForm.tsx`, `components/admin/TempPasswordResult.tsx`, `components/auth/RequirePasswordChangeGate.tsx`. Reuse existing UI primitives in `components/talent/ui/` (`Button`, `Input`, `Field`, `Select`, `Spinner`, `Textarea`).
- `middleware.ts` (root of `uis/backoffice`) for redirecting unauthenticated users (server-visible session check) — see §6.
- Test setup: `vitest.config.ts`, `vitest.setup.ts`, `playwright.config.ts`, `tests/` (or `__tests__/`), and example specs.
- `.env.example` (new) for the backoffice with server-only service URLs.

---

## 5. Files to Modify (under `uis/backoffice/`)

- `app/layout.tsx` — wrap children in `AuthProvider`; keep `uis/website` untouched.
- `components/BackofficeNavigation.tsx` — add **Account** and (admin-only) **User Management** (`/admin/users`) items, conditioned on `useAuth().user.role`; add a logout control.
- `lib/suppliers/api.ts`, `lib/incident-api.ts`, `lib/talent/api.ts` — repoint base URL to same-origin `/api/suppliers`, `/api/incidents`, `/api/talent`; add `credentials: "include"` + CSRF header on state-changing calls; on `401`, trigger global session-clear+redirect. Preserve the existing `parseAPIError`/field-error behavior.
- `package.json` — add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `@playwright/test`; add `test`, `test:watch`, `test:e2e` scripts.
- `README.md` (backoffice) — document the BFF, env vars, auth flows, and the deployment gate.

---

## 6. Route Protection

- **Protected** (require authenticated, active user): `/`, `/incidents`, `/suppliers*`, `/talent*`, `/account*`, `/admin*`.
- **Admin-only** (additionally `role="admin"`): `/admin/*` — backend still enforces 403 on `/api/users/*` admin routes regardless of UI.
- **Open:** `/login` (and, in Auth 3, `/forgot-password`, `/reset-password`).
- **Public site `uis/website`:** unaffected — no guard, no token, no redirect.

Mechanism: a combination compatible with the App Router and the BFF —
1. `middleware.ts` performs a cheap server-visible check (presence of the session/access cookie) to redirect obvious unauthenticated requests to `/login?next=<path>` (avoids redirect loops by excluding `/login`, `/api/auth/*`, static assets).
2. The `(protected)` layout / a server component calls `/auth/me` to **validate** (presence ≠ validity); on failure it clears cookies and redirects to `/login`.
3. `RequirePasswordChangeGate`: when `user.must_change_password` is true, force-navigate to `/account/change-password` and block other navigation until cleared, then restore access and return to `next` where practical.

---

## 7. Token Lifecycle (frontend)

- **Login:** `POST /api/auth/login` → backend sets HttpOnly cookies via the BFF → hydrate `AuthProvider` from `/auth/me` → redirect to the Back Office dashboard (or `next`). If `must_change_password`, redirect to `/account/change-password`.
- **Authenticated requests:** same-origin `/api/*` with `credentials:"include"` + CSRF header; cookies attached automatically.
- **Refresh:** on `401` from a protected call, the client attempts `POST /api/auth/refresh` once; on success retry, on failure clear + redirect.
- **Logout:** `POST /api/auth/logout` (server-side revoke) → clear cookies + auth state + any cached user data → redirect to `/login`.
- **Global `401`:** centralized handler clears state, redirects to `/login`, avoids loops and duplicate logout; preserves a safe `next` only by design.

No tokens in `localStorage`/`sessionStorage`. The browser never reads token contents for authorization.

---

## 8. Admin User Management + First-Login Flow

`/admin/users` (admin-only) supports: **Create user**, list, search/filter, view safe details (id, name, email, role, status, created/last-login), **suspend**, **disable**, **reactivate**, **revoke all sessions**. **Role editing deferred.**

**Create-user flow:** form (name + email) → `POST /api/users` → backend returns the **one-time temporary password** → `TempPasswordResult` shows it with a clear warning that **it cannot be retrieved later** and must be delivered securely to the user.

**First-login flow:** new user signs in at `/login` → `/auth/me` reports `must_change_password=true` → redirect to `/account/change-password`, normal navigation blocked → on success, `must_change_password=false`, normal access restored, returned to the originally requested route where practical.

---

## 9. Environment Configuration

Backoffice `.env.example` (server-only — **not** `NEXT_PUBLIC_`, so internal URLs and the BFF stay server-side):

```
IDENTITY_API_URL=http://localhost:8002
SUPPLIER_DIRECTORY_API_URL=http://localhost:8001
INCIDENT_PROCESSOR_API_URL=http://localhost:8000
TALENT_API_URL=http://localhost:8003
AUTH_COOKIE_SECURE=false   # false ONLY for local http://localhost; true in production
```

No JWT signing keys or secrets are exposed to the browser. Only genuinely public values may use `NEXT_PUBLIC_`. The legacy `NEXT_PUBLIC_*_API_URL` vars are superseded by same-origin `/api/*` routing.

---

## 10. Dependencies (documented; install only at implementation time)

`vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`, `@playwright/test`. No runtime auth library needed (cookies handled by the BFF + browser).

---

## 11. Testing Plan

**Vitest + React Testing Library** (component/unit) and **Playwright** (critical browser flows). Cover (Auth 2 requirements §11 + decisions):
- Login success / failure (generic error, no stale token).
- Token/cookie handling via BFF; Authorization/CSRF attached to protected requests; not attached to public-site requests.
- Protected-route redirect without a session; invalid-session redirect (presence ≠ validity).
- Public-site (`uis/website`) reachable without authentication.
- `/account/profile` load + update (name).
- Change-password validation (match, required, policy) + API success/failure.
- **Create user** (admin) → one-time temp password shown with warning; non-admin cannot reach `/admin/users` (UI) and `/api/users` returns 403.
- **First-login:** `must_change_password` forces `/account/change-password` and blocks navigation; cleared after change; returns to `next`.
- Logout clears state + prevents stale authenticated UI.
- Global `401` clears session + redirects; no redirect loops.
- Admin nav hidden for non-admins but backend 403 still enforced.

---

## 12. Manual Verification

1. (Admin, from Auth 1 CLI) log in at `/login`.
2. Open `/admin/users`, **Create user** → capture one-time temp password (note the warning).
3. Log out; visit a protected route while logged out → redirected to `/login`.
4. Log in as the new user → redirected to `/account/change-password`, navigation blocked.
5. Change password → normal access restored; protected data loads.
6. Open `/account/profile`; update name → persists.
7. Force/simulate a `401` (e.g. clear cookie) on a protected call → session cleared, redirected to `/login`.
8. Visit `uis/website` without authentication → fully usable.
9. As a normal user, attempt `/admin/users` and a direct `/api/users` call → blocked / 403.

---

## 13. Acceptance Criteria

- Login works end-to-end via the BFF; no `localStorage`/`sessionStorage` tokens.
- Protected requests carry cookies + CSRF; protected views redirect unauthenticated users; invalid/expired sessions cleared.
- Logout clears auth + redirects; global `401` clears session.
- Profile displays + updates name; change-password works against the Auth-1 contract and clears `must_change_password`.
- Admin-only `/admin/users` supports create/list/search/view/suspend/disable/reactivate/revoke-sessions; **role editing deferred**; **Create User present** (no public registration).
- First-login temp-password flow enforced (redirect + navigation block + restore).
- `uis/website` remains fully public; no standalone auth app created.
- Vitest + RTL + Playwright tests pass.
- **No Auth 3** (reset/email) work mixed in.
- **Production Authentication Deployment Checklist** satisfied before hosted deployment.

### Production Authentication Deployment Checklist (deployment gate)
`Secure=false` only on local `http://localhost`; hosted requires `Secure=true` + HTTPS.
- [ ] HTTPS enabled · [ ] cookies `Secure=true` · [ ] `HttpOnly=true` kept · [ ] `SameSite=Lax` kept · [ ] no broad cookie `Domain` (host-only) · [ ] correct prod frontend/service URLs · [ ] dev secrets/keys replaced · [ ] secrets only in deployment env (not committed) · [ ] reverse proxy recognizes HTTPS · [ ] trusted origins/CORS without wildcard+credentials · [ ] (Auth 3) reset links use prod HTTPS URL · [ ] post-deploy test of login/refresh/logout/CSRF/protected-routes/cookies.

---

## 14. Implementation Checklist

- [ ] Add Vitest + RTL + Playwright config and scripts.
- [ ] Build BFF route handlers under `app/api/*` (forward cookies/CSRF, relay Set-Cookie, map errors).
- [ ] `AuthProvider`/`useAuth` + server-side `/auth/me` bootstrap.
- [ ] `middleware.ts` + `(protected)` layout + `RequirePasswordChangeGate`.
- [ ] `/login`, `/account/profile`, `/account/change-password`, `/admin/users` (+ create).
- [ ] Repoint `lib/*/api.ts` to `/api/*` with credentials + CSRF + global 401 handling.
- [ ] Update `BackofficeNavigation` (account, admin-only user mgmt, logout).
- [ ] Backoffice `.env.example` (server-only URLs) + README.
- [ ] Tests per §11; manual verification per §12.
- [ ] Update engagement-tracking docs per AGENTS.md pre-commit workflow.

---

## 15. Decisions Requiring Approval (carried from the decision record)

- Post-login redirect destination (default: Back Office dashboard `/`, honoring `next`).
- Password policy enforced in the change-password form (default: ≥8 chars per NIST; backend authoritative).
- Whether `talent` gets a BFF route now (its backend isn't in the repo) or stays pointed at `TALENT_API_URL` until that service exists (default: BFF route stub that forwards to `TALENT_API_URL`).

---

## 16. Approval Gate

**Do not begin Auth 3 until Auth 2 is implemented, tested, reviewed, and approved.** No Auth 3 (forgot/reset pages, recovery link, email) work may be folded into this phase.
