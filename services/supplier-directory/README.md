# `services/supplier-directory/`

FastAPI service for the TrackFlow Supplier Directory subproject.

This is not Engagement 5. The Central API remains reserved for a future engagement under `services/central-api/`.

## Runtime

```bash
uv run --project services/supplier-directory uvicorn supplier_directory.main:app --reload --port 8001
```

The API exposes:

- `GET /health`
- `POST /suppliers`
- `GET /suppliers`
- `GET /suppliers/{id}`
- `GET /suppliers/{id}/contact`
- `PATCH /suppliers/{id}/rate`
- `PATCH /suppliers/{id}/status`
- `DELETE /suppliers/{id}`

`GET /health` is public. All `/suppliers` business endpoints require an Auth 1 RS256 access token from `trackflow_access` or `Authorization: Bearer`, and state-changing requests also require the double-submit `X-CSRF-Token` header matching the `trackflow_csrf` cookie.

## Seeding

The app seeds the demo supplier list on startup when the TinyDB file is empty.

You can also run the idempotent seed command:

```bash
uv run --project services/supplier-directory seed
```

The seed command deduplicates by supplier `name` + `country`.

## Storage

Set `SUPPLIER_DIRECTORY_DB_PATH` to choose where TinyDB persists data. Default:

```text
services/supplier-directory/data/suppliers.json
```

The generated database file is git-ignored.

## Contact Email Privacy

Default list and detail responses expose only `has_contact_email`. Raw `contact_email` is accepted on create and stored internally, but it is readable only through `GET /suppliers/{id}/contact`, which exists for this local demo and should be treated as privileged. The backoffice detail page uses this endpoint only after the user clicks the reveal control.

## CORS

Set `SUPPLIER_DIRECTORY_CORS_ORIGINS` to a comma-separated allowlist. Defaults:

- `http://localhost:3000`
- `http://127.0.0.1:3000`

Auth verifier environment variables:

- `IDENTITY_JWT_PUBLIC_KEY`
- `IDENTITY_JWT_ALGORITHM`
- `IDENTITY_JWT_ISSUER`
- `IDENTITY_JWT_AUDIENCE`

## Tests

```bash
uv run --project services/supplier-directory --extra dev pytest
```
