# Supplier Directory Subproject — Implementation Plan

## Context

TrackFlow's USA (Los Angeles) and Spain (Zaragoza) operations each track suppliers
in separate spreadsheets, so neither Carlos Vega (Carrier Ops) nor Ana Whitfield
(Warehouse Ops) has a unified view. The Supplier Directory is a **standalone
subproject** (spec: `docs/planning/supplier-directory.md`) that creates a centralized
supplier registry — a FastAPI backend + a `/suppliers` route in the existing
backoffice UI. It is explicitly **not** Engagement 5 and **not** the future Central
API; it mirrors the established Incident Report Processor pattern (`services/incident-processor/`
+ `uis/backoffice/app/incidents/`).

Confirmed decisions:
- **Contact email**: list/detail responses expose `has_contact_email` (bool) only. Raw
  email is accepted on POST and stored internally, readable solely via a privileged
  `GET /suppliers/{id}/contact` endpoint, documented as demo-only. This matches the
  backoffice README norm ("No customer emails should be rendered in the backoffice UI").
- **Seeding**: idempotent `uv run seed` command (dedupe by `name + country`) **plus**
  seed-if-empty on app startup so the demo never starts blank.

## Backend — `services/supplier-directory/`

Sibling of `services/incident-processor/`. Reuse that service's conventions: hatchling
build, Python ≥3.11, `create_app()` factory, `config.py` env reader, `constants.py` for
business rules, `[project.scripts]` console entry, pytest with `testpaths`/`pythonpath`.

Structure:
```
services/supplier-directory/
  README.md            # run commands, env vars, demo-only contact-email note
  pyproject.toml       # name "trackflow-supplier-directory"; deps: fastapi, uvicorn[standard], tinydb; dev: httpx, pytest; scripts: seed
  .env.example         # SUPPLIER_DIRECTORY_DB_PATH, SUPPLIER_DIRECTORY_CORS_ORIGINS
  supplier_directory/
    __init__.py        # export stable API via __all__
    main.py            # create_app(); routers; CORS via config; seed-if-empty on startup
    config.py          # get_db_path(), get_cors_origins() — env with localhost defaults
    constants.py       # VALID_CATEGORIES, VALID_STATUSES, COUNTRY->CURRENCY map
    models.py          # Pydantic: SupplierCreate, SupplierPublic, SupplierContact, RateUpdate, StatusUpdate + validators
    repository.py      # TinyDB access (insert/list/get/update/delete, dedupe by name+country)
    service.py         # business rules layer between routes and repository
    seed.py            # SUPPLIERS_SEED loader; entrypoint() for console script
  data/.gitkeep        # generated TinyDB json lives here, gitignored
  tests/
    test_api.py test_seed.py test_validation.py
```

Endpoints:
```
POST   /suppliers                 # accepts contact_email; returns SupplierPublic (no raw email)
GET    /suppliers                 # supports ?country= and ?category= filters
GET    /suppliers/{id}            # SupplierPublic
GET    /suppliers/{id}/contact    # privileged; returns raw contact_email (demo-only)
PATCH  /suppliers/{id}/rate       # updates rate_per_shipment + sets rate_updated_at
PATCH  /suppliers/{id}/status     # active | suspended
DELETE /suppliers/{id}
GET    /health
```

Models / validation (from spec `docs/planning/supplier-directory.md`):
- Fields: `name, country, categories, rate_per_shipment, currency, rate_updated_at, status, service_zone, contact_email, notes`.
- `country` ∈ {USA, Spain}; `currency` ∈ {USD, EUR}; **USA→USD, Spain→EUR** (reject mismatch).
- `status` ∈ {active, suspended}; `categories` ≥ 1 from `VALID_CATEGORIES` (8 strings in spec); `rate_per_shipment` > 0.
- `rate_updated_at` is system-generated (set on create and on every rate PATCH).
- `SupplierPublic` response model **omits** `contact_email`, includes `has_contact_email: bool`. `SupplierContact` model carries the raw email for the privileged endpoint only.

Storage: TinyDB persisted to `SUPPLIER_DIRECTORY_DB_PATH` (default `services/supplier-directory/data/suppliers.json`). Generated DB file gitignored; `data/.gitkeep` keeps the dir.

## Frontend — `uis/backoffice/`

Mirror the `app/talent/` + `lib/talent/` + `components/talent/` pattern (the definitive
client pattern in this repo).

- `app/suppliers/page.tsx` — server component; validate `searchParams` (country/category) with type guards, pass to client components. Wrap in `<AppShell>`.
- `components/suppliers/`: `SupplierDirectoryView.tsx`, `SupplierTable.tsx`, `SupplierFilters.tsx`, `SupplierForm.tsx`, `SupplierStatusBadge.tsx`, `RateUpdateControl.tsx`. Reuse existing UI primitives in `components/talent/ui/` (Button, Input, Select, Field, Spinner, Textarea) — import directly; do not duplicate.
- `lib/suppliers/`: `types.ts` (Supplier, Country, Currency, Status, APIError), `labels.ts` (value→display + semantic tone mappings, `isCountry`/`isCategory`/`isStatus` guards, category/status option arrays), `api.ts` (single `request<T>()` chokepoint with `cache: "no-store"`, defensive FastAPI `detail` error parsing, endpoint functions: list/get/create/patchRate/patchStatus/delete).
- Add nav entry to `components/BackofficeNavigation.tsx`: `{ label: "Suppliers", href: "/suppliers", icon: <lucide icon, e.g. Package> }`.
- Env var: `NEXT_PUBLIC_SUPPLIER_DIRECTORY_API_URL` (default `http://localhost:8001`), trailing-slash stripped — parallels `NEXT_PUBLIC_INCIDENT_PROCESSOR_API_URL`.

UI behavior (spec "What Carlos will see"):
- Table columns: name, country, categories, `rate_per_shipment` + currency, status, `service_zone` (when present), and a "Contact on file" indicator driven by `has_contact_email` (no raw email in the table).
- Filters (country, category) update URL/client state without page reload.
- Form submits via `POST /suppliers`; rate and status changes update the row after the API responds.
- Active vs suspended visually distinct via `SupplierStatusBadge` (reuse talent badge tone pipeline: value → tone → Tailwind classes).

## Repo tracking / docs (do NOT create a brief)

This is a subproject — follow the incident-processor doc pattern, not `docs/briefs/05-*.md`:
- Commit `docs/planning/supplier-directory.md` (currently untracked) as the source spec — matches tracked `docs/planning/incident-report-processor.md`.
- `services/README.md` — add `services/supplier-directory/` entry (note: not Engagement 5).
- `uis/backoffice/README.md` — document the `/suppliers` route + `NEXT_PUBLIC_SUPPLIER_DIRECTORY_API_URL` + demo-only contact-email note.
- `memory-bank/progress.md` — add a "Subprojects" bullet mirroring the incident-processor entry (name, spec path, locations, sensitivity note).
- `.gitignore` — add a context-commented entry for the generated TinyDB file (e.g. `services/supplier-directory/data/suppliers.json`), following the existing `# Generated local ...` style.
- Consider a `.agents/rules/` note only if contact emails are treated as sensitive local data; the privileged-endpoint design already keeps them out of default responses, so a full rule is optional.

## Verification

Backend (`uv run --project services/supplier-directory --extra dev pytest`):
- `test_seed.py`: seed inserts expected count (15); seed is idempotent (second run inserts 0).
- `test_validation.py`: POST rejects invalid status/category/currency/rate; USA+EUR and Spain+USD rejected; empty categories rejected.
- `test_api.py`: GET list returns all; `?country=` and `?category=` filters work; GET missing id → 404; PATCH rate updates `rate_updated_at`; PATCH status rejects invalid; DELETE missing id → 404; **default list/detail responses contain no raw `contact_email` (only `has_contact_email`)**; `GET /suppliers/{id}/contact` returns the raw email.

End-to-end demo (two long-running processes):
```bash
uv run --project services/supplier-directory uvicorn supplier_directory.main:app --reload --port 8001
npm run dev --workspace trackflow-backoffice
# seeding (idempotent):
uv run --project services/supplier-directory seed
```
Then load `http://localhost:3000/suppliers`: confirm seeded suppliers render, country/category filters work without reload, the create form posts a supplier, a rate update changes the row and bumps the timestamp, a status toggle flips the badge, and no raw email appears in the table (only "Contact on file").

Frontend checks: `npm run type-check`, `npm run lint`, `npm run build --workspace trackflow-backoffice` (per AGENTS.md pre-commit workflow for touched packages).
