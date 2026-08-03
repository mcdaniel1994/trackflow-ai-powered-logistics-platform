# `services/identity/`

FastAPI identity service for TrackFlow authentication.

This service owns TrackFlow Back Office users, password hashing, login, refresh rotation, logout, user-management APIs, and Auth 3 password reset/account recovery. It is not Engagement 5 and does not contain public registration.

## Runtime

```bash
uv run --project services/identity uvicorn identity.main:app --reload --port 8002
```

The API exposes:

- `GET /health`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- `GET /auth/me`
- `POST /auth/change-password`
- `POST /auth/forgot-password`
- `POST /auth/reset-password`
- `POST /users`
- `GET /users`
- `GET /users/{id}`
- `PUT /users/{id}`
- `PATCH /users/{id}/status`
- `POST /users/{id}/sessions/revoke`
- `DELETE /users/{id}`

Phase 3 also exposes the separate URL-issued OAuth surface:

- `GET /.well-known/oauth-authorization-server`
- `GET /oauth/jwks.json`
- `GET/POST /oauth/authorize`
- `POST /oauth/token`
- `POST /oauth/register` (local/Codespaces only by default)

There is no `/auth/register` endpoint. User creation is administrator-only through `POST /users`, and the first admin is created from the server CLI. When an admin creates a user, the API generates a one-time temporary password and automatically sends an account setup email with a time-limited password reset link when email delivery is configured. The temporary password is never emailed; it is returned once to the admin as a fallback if setup email delivery fails.

## OAuth 2.1 for MCP

OAuth tokens use `OAUTH_ISSUER_URL` as their URL issuer and expire after 15 minutes. Authorization
codes require S256 PKCE, expire after five minutes, are stored as SHA-256 hashes, and are burned on
their first redemption attempt. Identity issues no OAuth refresh tokens.

Supported scopes are `mcp:connect`, `incidents:read`, `incidents:write`, and `inventory:read`.
Authorization Code + PKCE supports public Playground clients. Confidential clients may use client
credentials or RFC 8693 token exchange; exchanges preserve or reduce scopes and require an exact
registered source audience and target resource.

Create confidential clients server-side. The generated secret is displayed once and only its
Argon2id hash is persisted:

```bash
uv run --project services/identity python -m identity.cli create-oauth-client \
  --name trackflow-mcp \
  --grants client_credentials,urn:ietf:params:oauth:grant-type:token-exchange \
  --scopes incidents:read,incidents:write,inventory:read \
  --resources https://api.example.test \
  --source-audiences https://mcp.example.test/mcp
```

`APP_ENVIRONMENT=local|codespaces` enables public dynamic registration by default;
`APP_ENVIRONMENT=production` disables it unless an operator explicitly overrides
`OAUTH_DYNAMIC_REGISTRATION_ENABLED`. Hosted issuers, redirect URIs, and resource identifiers must
use HTTPS. OAuth audit logs contain client ID, subject UUID, grant/outcome, and logger timestamp only.
Never log credentials, codes, bearer tokens, emails, consent form payloads, or client secrets.

Administrators may revoke a user's active refresh sessions without changing account status through `POST /users/{id}/sessions/revoke`. The route is CSRF-protected and intended for the Auth 2 Back Office user-management UI.

## Password Reset

Auth 3 adds public account-recovery endpoints:

- `POST /auth/forgot-password` accepts an email address and always returns the same success response for valid input.
- `POST /auth/reset-password` accepts an opaque reset token and a new password.

Reset tokens are cryptographically random, stored only as SHA-256 hashes in TinyDB's `password_resets` collection, expire after `RESET_TOKEN_EXPIRE_MINUTES` (default 30, allowed range 15-60), and are single-use. A successful reset stores a new Argon2id password hash, clears `must_change_password`, invalidates outstanding reset tokens for that user, and revokes all refresh sessions.

Reset emails are sent through Resend using environment-only configuration:

```bash
RESEND_API_KEY=
EMAIL_SENDER=no-reply@trackflow.example
FRONTEND_BASE_URL=http://localhost:3000
RESET_TOKEN_EXPIRE_MINUTES=30
```

`FRONTEND_BASE_URL` must be the HTTPS Back Office origin in hosted environments so reset links are generated for the correct public app. Do not log reset tokens, reset links, email API keys, password values, or password hashes.

## First Admin

```bash
uv run --project services/identity python -m identity.cli create-admin
```

The command prompts for the admin name, email, and password, refuses duplicate email addresses, stores only an Argon2id hash, and never prints the password.

After restoring a TinyDB backup, clear restored session/reset state before the
required RS256 key rotation:

```bash
uv run --project services/identity python -m identity.cli revoke-sessions
```

## RS256 Keys

Generate a local keypair for development:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Set `IDENTITY_JWT_PRIVATE_KEY` only for this service. Set `IDENTITY_JWT_PUBLIC_KEY` for this service and for every domain service that validates access tokens. In `.env` files, multiline PEM values can be represented with escaped `\n` characters.

Always preserve the complete PEM framing, including the exact
`-----BEGIN ...-----` and `-----END ...-----` lines. In Coolify, paste each
complete value without a variable name or surrounding quotes and enable
Multiline. Identity parses both RSA keys and verifies that they match during
startup; incomplete, malformed, mismatched, or non-RS256 configuration prevents
the service from becoming healthy.

## Storage

Set `IDENTITY_DB_PATH` to choose where TinyDB persists data. Default:

```text
services/identity/data/identity.json
```

The generated database file is git-ignored.

TinyDB has no SQL-level transactions, constraints, or indexes. Auth 1 coordinates writes in repository methods and must run the identity service as a single worker until SQL or a tested file-locking strategy replaces it.

Database and persistent-storage changes in this service must follow
[`docs/standards/database-engineering-standard.md`](../../docs/standards/database-engineering-standard.md).

## Cookies And CSRF

Login sets:

- `trackflow_access` - HttpOnly access-token cookie, 15 minutes.
- `trackflow_refresh` - HttpOnly refresh-token cookie, 14 days.
- `trackflow_csrf` - non-HttpOnly double-submit CSRF cookie.

Local HTTP uses `AUTH_COOKIE_SECURE=false`. Hosted deployments must use HTTPS and `AUTH_COOKIE_SECURE=true`.

## Tests

```bash
uv run --project services/identity --extra dev pytest
```
