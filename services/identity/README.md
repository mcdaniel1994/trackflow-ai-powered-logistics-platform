# `services/identity/`

FastAPI identity service for Auth 1.

This service owns TrackFlow Back Office users, password hashing, login, refresh rotation, logout, and user-management APIs. It is not Engagement 5 and does not contain password reset or frontend authentication work.

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
- `POST /users`
- `GET /users`
- `GET /users/{id}`
- `PUT /users/{id}`
- `PATCH /users/{id}/status`
- `DELETE /users/{id}`

There is no `/auth/register` endpoint. User creation is administrator-only through `POST /users`, and the first admin is created from the server CLI.

## First Admin

```bash
uv run --project services/identity python -m identity.cli create-admin
```

The command prompts for the admin name, email, and password, refuses duplicate email addresses, stores only an Argon2id hash, and never prints the password.

## RS256 Keys

Generate a local keypair for development:

```bash
openssl genrsa -out private.pem 2048
openssl rsa -in private.pem -pubout -out public.pem
```

Set `IDENTITY_JWT_PRIVATE_KEY` only for this service. Set `IDENTITY_JWT_PUBLIC_KEY` for this service and for every domain service that validates access tokens. In `.env` files, multiline PEM values can be represented with escaped `\n` characters.

## Storage

Set `IDENTITY_DB_PATH` to choose where TinyDB persists data. Default:

```text
services/identity/data/identity.json
```

The generated database file is git-ignored.

TinyDB has no SQL-level transactions, constraints, or indexes. Auth 1 coordinates writes in repository methods and must run the identity service as a single worker until SQL or a tested file-locking strategy replaces it.

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
