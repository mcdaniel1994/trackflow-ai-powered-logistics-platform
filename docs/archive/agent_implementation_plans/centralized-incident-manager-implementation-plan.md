# Centralized Incident Manager Implementation Plan

**Approved:** July 2, 2026  
**Primary source:** `docs/planning/centralized-incident-manager.md`  
**Delivery type:** TrackFlow subproject, not a numbered engagement

## Summary

Build the incident manager as a PostgreSQL-backed domain inside Central API and
replace the Back Office CSV-upload page with a real-time incident dashboard.
Preserve the existing incident analyzer service and CLI as historical tools.

## Backend and persistence

- Add an incidents domain using the existing router → service → repository →
  SQLModel structure.
- Add an Alembic migration for required incident fields, UTC timestamps,
  nullable server-derived reporter UUID, a nullable unique import hash,
  database enum constraints, and filter/sort indexes.
- Start browser incidents at `open`, enforce the documented transition graph
  under a row lock, and keep final states immutable.
- Require Identity authentication for reads and authentication plus CSRF for
  writes.

## API

- `POST /api/incidents`
- `GET /api/incidents` with status, origin, branch, and category filters plus
  bounded pagination
- `GET /api/incidents/{id}`
- `PATCH /api/incidents/{id}/status`
- `GET /api/incidents/summary`
- Return field-keyed HTTP 400 validation errors for incident routes, safe 404
  and transition errors, safe 503 persistence failures, and a generic 500
  boundary without internal detail.

## Historical import and shared validation

- Add `packages/trackflow_incidents/` for canonical enums, privacy-safe legacy
  CSV validation, and deterministic normalization.
- Refactor the historical processor to consume the package without changing
  its API, CLI, or aggregate output contracts.
- Add an idempotent Central API seed and `scripts/seed_incidents.py`; hash the
  source incident ID and never store or print customer email values.
- Normalize legacy categories and statuses exactly as approved, preserve the
  source date at midnight UTC, and assign `customer`/`central` defaults.

## Back Office

- Replace the upload view with a touch-friendly registration form, independent
  summary/list/form states, operational filters, exact branch labels, and
  direct valid status actions.
- Repoint the allowlisted same-origin incident BFF to Central API.
- Validate before submission, show safe field messages, clear on success, show
  explicit loading/empty/retry states, and roll back failed optimistic status
  updates.

## Verification and documentation

- Cover schema constraints, migration rollback, authentication/CSRF, creation,
  filtering, pagination, lifecycle transitions, summaries, safe failures,
  legacy mappings, seed repeatability, and analyzer regression.
- Cover BFF allowlisting, client validation, independent failure states,
  filtering, empty results, and optimistic rollback.
- Run Python lint/type/build/tests/coverage plus Back Office type-check, lint,
  build, Vitest, and targeted browser smoke.
- Update project progress and folder documentation without creating or
  modifying a numbered engagement brief or roadmap row.
