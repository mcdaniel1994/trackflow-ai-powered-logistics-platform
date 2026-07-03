# TrackFlow — Dockerization & Deployment Architecture Plan

> **Implementation status (July 2026):** repository phases 2-5 and the
> owner-approved website link are implemented and locally verified. External
> phases 1 and 6-12 remain approval-gated; the Supplier Directory rollback
> service remains intact until its production observation window closes.
> **Rev 3** — incorporates two external (Codex) review passes; every accepted correction was re-verified against the repo/current docs before inclusion.
> Legend: **[FACT]** = verified from the repo · **[REC]** = recommendation (judgment) · **[ASSUMPTION]** = needs confirmation.

---

## Context — why this change

TrackFlow's public site (`uis/website/`) ships on Vercel, but **[FACT]** the backend services (`services/*`) have *no deployment path* — `docs/runbooks/README.md` and `docs/standards/production-readiness.md` list backend deployment, rollback, health checks, monitoring, and backup/restore as tracked gaps. There are **zero application Dockerfiles**, **zero CI workflows**, and the only container artifact is a *disposable* local Postgres (`services/central-api/compose.yml`, `postgres:17-alpine`, tmpfs). We now have a VPS (Hostinger KVM 2, Ubuntu 24.04, **2 vCPU / 8 GB / 100 GB**) with Docker + Traefik + Coolify installed and the `forgehub.cloud` domain. Goal: Dockerize the backend, restructure for scalable local dev + production, keep the public site on Vercel, and deploy the internal Back Office + backend through Coolify — without breaking the same-origin BFF, HttpOnly auth cookies, or CSRF forwarding.

**Owner decisions (confirmed):**
1. **No external API consumer** — backend stays private; **no `api.forgehub.cloud`**.
2. **Deploy Identity + Central API (inventory + incidents + suppliers) + Back Office.**
3. **Back Office runs on Coolify** (co-located → BFF↔service calls stay on the private Docker network).
4. **Identity stays on TinyDB** (sole owner, single replica/worker, persistent volume, backups + tested restore, Postgres migration on the roadmap).
5. **Supplier Directory is folded into Central API** as a Postgres-backed `suppliers` domain — an explicit, *documented* waiver of the `services/README.md` boundary (see §4/§11).
6. **Coolify deploy unit = one Compose stack** (separate from local dev compose; rollback is stack-level — accepted, §9).
7. **Incident Report Processor subproject fully retired** — the FastAPI service, the `analyze.py` CLI, and the importable `incident_processor` package all go (see §4). Prod incidents **start empty**; `seed-incidents` stays a dev-only tool (no CSV enters any image).
8. **Container builds run in GitHub Actions** and publish to GHCR; the VPS pulls
   commit-pinned images instead of compiling them.
9. **Portfolio durability waiver:** Supabase Free and Identity TinyDB have no
   scheduled backups for now. Their data is explicitly disposable and recovery
   is recreation, migration, and reseeding; this is not production-grade
   durability.

> **Build-time is the real VPS constraint** **[FACT/DECISION]**: 2 vCPU/8 GB
> handles this runtime at modest traffic, but memory-hungry Next 16/React 19
> builds now run on GitHub-hosted Actions runners and publish to GHCR.

---

## 1. Current architecture summary  **[FACT]**

**Monorepo:** npm workspaces (root globs `packages/*`, `uis/*`; no turbo/nx). Node pinned **22** (`.nvmrc`). Python services are isolated `uv` projects (`>=3.11`, hatchling), **not** workspace members.

**Node surfaces**
- `uis/website/` — public Next.js **16.2.6** App Router, **no env vars**, no Back Office link, default output → Vercel-native.
- `uis/backoffice/` — internal Next.js **16.2.6** App Router **BFF**. Browser calls only same-origin `/api/*`; `lib/server/proxy.ts` (`proxyRequest`) fetches upstreams server-side (`no-store`, `redirect: manual`, 15 s timeout, 504/503). Consumes `@repo/shared-types` as **TS source** via `transpilePackages`. Middleware `proxy.ts` **redirects every cookieless path except `api|_next/static|_next/image|favicon.ico`** to `/login` ([proxy.ts:33](uis/backoffice/proxy.ts#L33), verified) → a health route must live under `/api`. **No `/health` route today.**

**Auth / BFF wiring** — server-only env (no `NEXT_PUBLIC_*`): `IDENTITY_API_URL` · `CENTRAL_API_URL` · `SUPPLIER_DIRECTORY_API_URL` · `INCIDENT_PROCESSOR_API_URL` (**defined but unused**) · `TALENT_API_URL` (external). Cookies `trackflow_access`/`trackflow_refresh` (HttpOnly) + `trackflow_csrf` (JS-readable) → `X-CSRF-Token` double-submit; `AUTH_COOKIE_SECURE` env-driven (**must be `true` on HTTPS**). Only `/api/auth` relays `Set-Cookie`.

**Python services**
- `services/identity/` — FastAPI + **TinyDB** (sole owner), RS256 **private** key + Argon2id + Resend. `threading.RLock` → **single worker only** ([README:84](services/identity/README.md#L84)). CLI `create-admin` exists; **no revocation CLI yet**.
- `services/central-api/` — FastAPI + **SQLModel/Alembic/PostgreSQL**; domains **inventory** + **incidents**. **psycopg2** driver. Alembic head `20260702_0002`; env.py `NullPool`. `/health` runs `SELECT 1`→503. **No TLS/sslmode in code today.** `seed-inventory` requires `SEED_USER_UUID` = **an existing Identity user** ([README:84/89](services/central-api/README.md#L89), verified). `seed-incidents` reads `services/incident-processor/tests/fixtures/sample-incidents.csv` ([README:53](services/central-api/README.md#L53)).
- `services/supplier-directory/` — FastAPI + **TinyDB** (`suppliers`), seeds on startup, single worker. `SupplierPublic` omits contact email, exposes `has_contact_email: bool` ([models.py:96](services/supplier-directory/supplier_directory/models.py#L96), verified).
- `services/incident-processor/` — FastAPI, in-memory only. **Live dependents (verified):** central-api `tests/test_incidents.py:14` + README:53 read its fixture; `scripts/analyze.py:7` does `from incident_processor.cli import entrypoint`; `conftest.py:15-32` gates collection on `find_spec("incident_processor")`; `packages/trackflow_incidents/README.md:11` + `scripts/README.md` reference it. → **cannot be deleted naively.**

**Rules:** boundary — each service owns its persistence/lifecycle/failure boundary ([services/README.md:7-16](services/README.md#L7-L16)); retirement — retired code is **deleted**, preserved via a `docs/archive/` note + git, not kept on disk ([AGENTS.md:44](AGENTS.md#L44)).

**Standards binding this plan:** secrets via env/secret store only; HTTPS + `AUTH_COOKIE_SECURE=true` hosted; encrypted remote DB + least-privilege identities; CORS allowlist; health/liveness per service; RPO/RTO + verified restore for non-disposable data; **migrations/seeds explicit + approval-gated, never app-startup**.

---

## 2. Recommended local-development architecture  **[REC]**

One **root `compose.yaml`** (local dev **only**) against a **disposable** local Postgres. Root `.env` (git-ignored) + committed `.env.example`; per-service `.env.example` remain contracts.

- `postgres` (postgres:17-alpine, tmpfs, `pg_isready`); `identity` (TinyDB named volume, single worker); `central-api` (`DATABASE_URL`→local pg, depends_on healthy); `backoffice` (service-name URLs, `AUTH_COOKIE_SECURE=false`).
- **`migrate` / `seed`** — one-off services under `profiles: [setup]`; run `alembic upgrade head` then `seed-*` and exit; **never** app-startup. Website is **not** containerized.

---

## 3. Recommended production topology  **[REC]**

```
                 ┌───────────────────── Vercel ─────────────────────┐
  forgehub.cloud │  uis/website  (public Next.js, @vercel/analytics) │
  www.forgehub…  └───────────────────────────┬─────────────────────┘
                                              │ top-right "Back Office Login" →
                                              ▼
        ┌──────────── Hostinger VPS · Coolify · Traefik ────────────┐
        │  Traefik (TLS :80/:443)                                   │
        │   └─ backoffice.forgehub.cloud ─► backoffice (Next :3000) │
        │        ── private Coolify network (Coolify-created) ──    │
        │   identity(:8000, volume) ◄─┐   central-api(:8000)        │
        │                             └─ BFF server-side fetch ─┘   │
        └───────────────────────────────────┬──────────────────────┘
                                             │ TLS (sslmode=require)
                                             ▼
                        Supabase Postgres (managed, NOT containerized)
                        runtime → session/direct :5432 (small pool, DML role)
                        migrations/seeds → direct :5432 (or session fallback), one-off only
```

- **Only `backoffice.forgehub.cloud` is public.** Identity + Central API have **no Traefik route** and **no host-published ports**. **No `api.forgehub.cloud`.** Supabase external/managed.

---

## 4. Service, container & retirement boundaries  **[REC]**

**Central API absorbs Suppliers** (`suppliers` domain). Explicit, documented waiver of `services/README.md` (recorded in the migration brief, §12). `/suppliers` paths + `has_contact_email` privacy contract preserved by mounting the router unchanged.

**Production containers (3):**
| Container | Contents | State | Public? | Workers |
|---|---|---|---|---|
| `backoffice` | Next.js standalone BFF | none | **Yes** (Traefik TLS) | Next default |
| `central-api` | inventory + incidents + **suppliers** | Supabase (external) | No | can scale later |
| `identity` | auth, RS256 issuer | **TinyDB volume** | No | **1 only** |

Plus **`central-api-migrate` / seed** — one-off, **not in the auto-deployed stack** (see §6/§9). Do NOT fold Identity into Central API (single-worker, holds the signing key).

**Incident Report Processor retirement (dependency-extraction FIRST, then delete):**
1. Move the fixture → `services/central-api/tests/fixtures/sample-incidents.csv`; update `tests/test_incidents.py:14` + central-api README:53 + `packages/trackflow_incidents/README.md:11` to the new path.
2. Delete `scripts/analyze.py` and remove its refs from `scripts/README.md` (the CLI is retired).
3. Remove the `incident_processor` branch from `conftest.py` (lines ~15-32).
4. Delete `services/incident-processor/`; drop the unused `INCIDENT_PROCESSOR_API_URL` from the BFF.
5. Add `docs/archive/incident-report-processor-retirement.md` (delete + note; preserve via git). **Archived planning docs keep their historical paths — do not rewrite history.**
*Gate:* `rg -n "incident.processor|incident_processor"` returns only archived-doc references; central-api tests green against the moved fixture.

---

## 5. Environment-variable & secret-management strategy  **[REC]**

- **Local:** root `.env` (git-ignored) + `.env.example`. **Audit `.gitignore`** — `.env` files exist on disk for identity/central-api/backoffice; verify none tracked, **rotate anything ever committed**.
- **Production:** all secrets in **Coolify's env/secret UI** (build-time vs runtime + BuildKit secrets); nothing sensitive in image layers.
- **Key split:** only `identity` gets `IDENTITY_JWT_PRIVATE_KEY`; central-api gets the **public** key only.
- **Least-privilege DB roles (2, dedicated login roles — not the Supabase superuser):**
  - **runtime DML** (`DATABASE_URL`) — app traffic **and seeds**. Grants: `USAGE` on schema, `SELECT/INSERT/UPDATE/DELETE` on tables, `USAGE` on sequences.
  - **migration DDL** (`MIGRATION_DATABASE_URL`) — Alembic only. Runs `ALTER DEFAULT PRIVILEGES … GRANT … TO <runtime>` so future migrated tables/sequences are reachable by the runtime role.
- **Supavisor username:** use the **exact pooler connection string/username from the Supabase dashboard** (do not hardcode a `postgres.<ref>` format).
- **Timeouts:** psycopg2 `connect_timeout` + PostgreSQL `statement_timeout`/`lock_timeout` on the central-api engine; keep the BFF 15 s upstream timeout.
- **CORS/cookies hosted:** origins = `https://backoffice.forgehub.cloud` only; `AUTH_COOKIE_SECURE=true`; `SAMESITE=lax`; **host-only cookies, no `Domain`**; `FRONTEND_BASE_URL=https://backoffice.forgehub.cloud`.

---

## 5a. Proposed repository architecture tree  **[REC]**

`＋`=new · `~`=modified · `⌦`=deleted (retirement note kept). Unchanged files elided.

```
trackflow/
├── compose.yaml                         ＋ LOCAL DEV ONLY (postgres tmpfs + services, host ports, profiles:[setup])
├── compose.coolify.yaml                 ＋ PROD stack (NO host ports, NO custom network; migrate/seed behind inactive profile)
├── .env.example  / .dockerignore(ROOT)  ＋ root context; ignore .env*, **/data/*.json, *.csv, .git, node_modules, .next, caches
├── conftest.py                          ~ remove incident_processor branch
├── scripts/
│   ├── analyze.py                       ⌦ deleted (Incident Report Processor CLI retired)
│   └── README.md                        ~ drop incident-processor refs
│
├── docker/{identity,central-api,backoffice}.Dockerfile  ＋ context=repo root, non-root, --init, HEALTHCHECK
│
├── uis/
│   ├── website/  app/(header)           ~ top-right "Back Office Login" (NEXT_PUBLIC_BACKOFFICE_URL); via visibility.md
│   └── backoffice/
│       ├── next.config.ts               ~ output:"standalone" + outputFileTracingRoot: repo root
│       ├── app/api/health/route.ts      ＋ health endpoint (under /api → NOT redirected by proxy.ts) + test: 200 not 307
│       ├── lib/server/service-urls.ts   ~ suppliers→CENTRAL_API_URL; drop SUPPLIER_DIRECTORY_API_URL + INCIDENT_PROCESSOR_API_URL
│       └── .env.example                 ~ internal service names + AUTH_COOKIE_SECURE=true
│
├── packages/trackflow_incidents/README.md  ~ fixture path → central-api/tests/fixtures
│
├── services/
│   ├── identity/
│   │   ├── identity/cli.py              ~ + revoke-sessions command (clears refresh_sessions + password_resets)
│   │   └── data/identity.json               (persistent Coolify volume in prod; readiness verifies it's writable)
│   ├── central-api/
│   │   ├── central_api/main.py          ~ include suppliers_router
│   │   ├── central_api/core/config.py   ~ + MIGRATION_DATABASE_URL, sslmode=require, timeouts
│   │   ├── central_api/db/session.py    ~ small session-mode-safe pool + timeouts
│   │   ├── central_api/domains/suppliers/{models,schemas,repository,service,router,seed}.py  ＋
│   │   ├── migrations/env.py            ~ read MIGRATION_DATABASE_URL
│   │   ├── migrations/versions/…0003_suppliers_schema.py  ＋ (rate/country-currency/status/uniqueness invariants)
│   │   ├── scripts/import_suppliers_from_tinydb.py  ＋ idempotent; preserves UUIDs/rate_updated_at/nulls/ordering/filters/contracts
│   │   ├── tests/fixtures/sample-incidents.csv  ＋ (moved from incident-processor)
│   │   ├── tests/test_incidents.py      ~ fixture path
│   │   ├── pyproject.toml               ~ + seed-suppliers
│   │   ├── README.md                    ~ fixture path; note prod incidents start empty
│   │   └── compose.yml                  ⌦ folded into root compose.yaml
│   ├── supplier-directory/             ⌦ deleted AFTER fold verification + observation (retirement note)
│   └── incident-processor/             ⌦ deleted now, after dependency extraction (retirement note)
│
└── docs/
    ├── planning/{deployment-dockerization, supplier-directory-postgres-migration}.md  ＋ (canonical brief + waiver brief)
    ├── runbooks/{backend-coolify-deployment, supabase-migrations, identity-tinydb-backup-restore}.md  ＋
    └── archive/{incident-report-processor-retirement, supplier-directory-retirement}.md  ＋
```

---

## 6. Docker, Dockerfile & Compose structure  **[REC]**

**Two Compose files, never shared.** Root `compose.yaml` = local dev (tmpfs pg, host ports, `profiles:[setup]`). `compose.coolify.yaml` = prod: **no `ports:` for private services, no custom `networks:`** (Coolify auto-creates the isolated bridge; reach services by name). **`migrate`/`seed` sit behind an inactive profile so a normal deploy never starts them** (`exclude_from_hc` only affects health evaluation, not startup) — run them as **explicit one-off Coolify commands** (documented exact invocation).

**Python Dockerfiles** (context=repo root): `uv` image + `python:3.11-slim`, multi-stage; copy `packages/trackflow_auth` (+`trackflow_incidents` for central-api) + service `pyproject.toml`/`uv.lock`; `uv sync --frozen --no-dev`; **non-root**, `--init`/`tini`, dropped caps; `EXPOSE 8000`; `CMD uvicorn <pkg>.main:app --host 0.0.0.0 --port 8000 --workers 1`; `HEALTHCHECK`→`/health`.

**backoffice Dockerfile** (context=repo root): `output:"standalone"` **+ `outputFileTracingRoot`=repo root** (traces `@repo/shared-types`); multi-stage `node:22`; **manually copy `public/` and `.next/static`** into standalone output; `node server.js` on 3000, non-root; health at **`app/api/health/route.ts`** (under the proxy-excluded `/api` prefix) with a test asserting **200, not 307**.

**Hardening:** memory/CPU limits, log rotation, non-root, read-only rootfs where feasible. **Root `.dockerignore`** excludes `.env*`, `**/data/*.json`, `*.csv`, `.git`, `node_modules`, `.next`, caches, tests. (Broad `*.csv` exclusion is fine — prod does not seed incidents, so no fixture needs to enter an image.)

---

## 7. Supabase runtime & migration connection strategy  **[REC]**

Central API is a **persistent server holding a SQLAlchemy/psycopg2 pool — not a serverless client** → hold real connections, not the serverless transaction pooler.

| Purpose | Mode / port | Pool | Role |
|---|---|---|---|
| **Runtime** (central-api) | **Direct :5432** if IPv6/IPv4-add-on reachable, else **Supavisor Session :5432** | small `QueuePool` + `pool_pre_ping` + `pool_recycle` | **runtime DML** |
| **Migrations + seeds** | **Direct :5432** preferred, else **Session :5432** | `NullPool` (already) | migrations use **DDL**; seeds use **DML** |

- **Not** transaction mode (6543). Differentiation is by **role + pool + lifecycle** (and mode when direct is reachable). psycopg2 doesn't use asyncpg-style server-side prepared statements, so that hazard is largely moot; the pooling-model mismatch is the reason to avoid transaction mode.
- **TLS:** `?sslmode=require` on both (optionally `verify-full` + Supabase CA). Use the **dashboard-provided** pooler connection string.
- **[ASSUMPTION]** VPS IPv4/IPv6 decides direct-vs-session — confirm before wiring.
- First Supabase migration/seed **approval-gated**: confirm target, take a logical `pg_dump` first.

---

## 8. DNS, networking, firewall, monitoring & backup plan  **[REC]**

**DNS:** `forgehub.cloud` + `www` → **Vercel** using **exact dashboard records**; `backoffice.forgehub.cloud` → **A → VPS** (Traefik ACME). **No `api` record.**

**Firewall (currently MISSING) — Coolify-safe:** use **Hostinger's network firewall** (Docker bypasses host UFW). Keep Coolify's **8000, 6001, 6002** reachable **until the Coolify dashboard has its own domain + HTTPS**, then close. Allow `443` (+`80` ACME), `22` restricted; deny all else.

**Portfolio waiver (owner-confirmed July 2026):** the following remains the
production-grade target, but scheduled backups and restore drills are deferred
while all deployed data is treated as disposable.

**Production-grade backup target:**
- **Identity TinyDB:** consistency-safe capture (quiesce the single writer / snapshot the volume, not a naive live-file copy), validate JSON, restore into an **isolated** env to prove it, store **off-box** (Coolify's own backup excludes volume data). **Post-restore security step (define it, doesn't exist yet):** an `identity revoke-sessions` CLI (clears the `refresh_sessions` + `password_resets` TinyDB tables) **plus RS256 signing-key rotation** (new keypair → update `IDENTITY_JWT_PRIVATE_KEY` on identity + `IDENTITY_JWT_PUBLIC_KEY` on central-api), which also invalidates outstanding access tokens. Restoring an old auth DB otherwise resurrects revoked sessions/used reset tokens/disabled users.
- **Supabase:** enable the **actual purchased tier** (daily and/or PITR); keep an off-site `pg_dump` before risky DDL; document RPO/RTO. Whole-project restore = downtime + omits custom-role passwords → **last resort**.
- **VPS** backups on; Coolify config backed up off-site.

**Monitoring:** Coolify health checks → each `/health` (+ backoffice `/api/health`); uptime monitor on `backoffice.forgehub.cloud`; ship/rotate logs; never log tokens/connection strings/PII.

---

## 9. Coolify deployment order & rollback  **[REC]**

**Order — Identity/admin before any inventory seed (`seed-inventory` needs an existing Identity UUID):**
1. Supabase project + runtime(DML) & migration(DDL) roles; secrets → Coolify; verify TLS.
2. Acknowledge the portfolio durability waiver; revisit backup/restore before
   storing meaningful production data.
3. **Run migrations** (`central-api-migrate`, DDL role) — explicit one-off; `pg_dump` first; approval-gated.
4. Deploy **identity** (volume, `AUTH_COOKIE_SECURE=true`) → `/health` green.
5. **Bootstrap the production admin** (`create-admin`), **capture the stable Identity UUID**.
6. **Seed inventory** (explicit, DML role, `SEED_USER_UUID`=that UUID), then **seed suppliers**. **Do NOT seed incidents** (prod starts empty).
7. Deploy **central-api** (runtime DML role) → `/health` `database: ok`.
8. Deploy **backoffice** → verify login → cookie → CSRF → inventory/incidents/suppliers over HTTPS.
9. DNS + website Back Office Login link (via visibility standard).

**Rollback (single Coolify Compose stack — accepted tradeoff):** lifecycle is **stack-level**; Coolify rolls the stack back to the previous retained images. Migrations never auto-run, so a stack rollback never implies a schema rollback. Prefer **expand/contract migrations + forward fixes**; avoid unconditional `alembic downgrade` — a bad migration → forward fix, or last-resort `pg_dump`/PITR restore (approval-gated). Identity rollback = restore volume **then run the revocation + key-rotation step**.

---

## 10. Phased implementation plan with verification gates  **[REC]** (12-step order)

1. **Infra decisions + safety baseline.** Supabase Free/us-east-2 via IPv4
   Session pooler, disposable-data waiver, `coolify.forgehub.cloud`, and
   GitHub Actions/GHCR builds are confirmed. Resend sender and Supplier TinyDB
   authority remain open. Attach the Hostinger firewall only after separate
   approval. *Gate:* `git ls-files | rg '\.env$'` empty; firewall on without
   locking out Coolify.
2. **Incident Processor dependency extraction + retirement** (per §4). *Gate:* fixture moved; `rg incident_processor` → only archived docs; central-api tests green.
3. **Local Docker images + local Compose verify.** Dockerfiles (non-root, healthchecks), backoffice `standalone`+tracing+`app/api/health` (test 200), root `compose.yaml` `profiles:[setup]`, root `.dockerignore`. *Gate:* `docker compose up` healthy; `--profile setup run migrate` applies head; login + inventory + incidents work locally.
4. **Supplier domain + migration verification** (the boundary-waiver brief). `suppliers` domain + `0003` migration (invariants) + `seed-suppliers`; idempotent TinyDB→Postgres importer (preserve UUIDs/`rate_updated_at`/nulls/ordering/filters/error contracts + `has_contact_email`); re-point BFF `/api/suppliers`→`CENTRAL_API_URL`; define write-freeze (or dual-write) for cutover. *Gate:* backoffice supplier regression green; importer count+field verification matches; original `suppliers.json` untouched.
5. **Production Compose + runbooks.** `compose.coolify.yaml` (no host ports/custom net; migrate/seed inactive profile), resource limits, log rotation, secrets matrix; write the 3 runbooks incl. the revocation procedure.
6. **Supabase roles/bootstrap + staging migration test.** Create
   runtime/migration roles + default-privilege grants; test migration on a
   disposable/staging target. Restore drills are waived for the disposable
   portfolio deployment. *Gate:* staging migration succeeds.
7. **Production schema migration** (explicit one-off, `pg_dump` first, approval-gated).
8. **Deploy Identity + admin bootstrap** (`AUTH_COOKIE_SECURE=true`); capture UUID. *Gate:* `/health` green; admin can authenticate.
9. **Explicit inventory + supplier seeds** (DML role). *Gate:* row counts verified; **no incident seed**.
10. **Deploy Central API + Back Office.** *Gate:* HTTPS login sets `Secure; HttpOnly` cookies; CSRF + password reset work; all `/health` green; internet `curl` to backend hosts fails (only backoffice serves).
11. **DNS + optional website link.** Apex/www→Vercel (dashboard records); `backoffice.`→VPS; add Back Office Login (owner-approved) after routing through `docs/standards/visibility.md`.
12. **Supplier Directory retirement after observation window.** After successful prod observation + rollback-window close, **delete** `services/supplier-directory/` (+ untouched `suppliers.json`) with a retirement note. *Gate:* **no active runtime, test, script, or current-documentation references** (archived docs may retain historical paths); docs updated.

---

## 11. Risks, tradeoffs & unresolved decisions

- **[ACCEPTED TRADEOFF] Supplier fold-in** waives the independent-service boundary → justified in the migration brief; enlarges Central API blast radius.
- **[ACCEPTED TRADEOFF] Single Coolify Compose stack** → stack-level rollback.
- **[FACT/RISK] Build-time CPU/memory** on 2 vCPU/8 GB — serialize builds / limits / CI if unstable.
- **[FACT/RISK] Identity single-worker TinyDB** — backup/restore + revocation + key-rotation are the only safety net; Postgres migration on the roadmap.
- **[RISK] First Supabase migration/seed** destructive-capable + approval-gated; `pg_dump` first.
- **[ASSUMPTION] VPS IPv4/IPv6** decides direct-vs-session.
- **[GOVERNANCE] Public Back Office link** changes delivered public behavior → visibility standard applies (owner requested it).
- **[OPEN]** Quality/security CI remains incomplete even though container image
  builds now run in GitHub Actions. Add secret scanning before production
  secrets land.

**Remaining Phase-1 owner inputs:** verified Resend production sender; whether
existing Supplier TinyDB data is authoritative or regenerable.

---

## 12. Exact files to create / modify / delete

**Create:** `docker/{identity,central-api,backoffice}.Dockerfile`; root `.dockerignore`, `compose.yaml`, `compose.coolify.yaml`, `.env.example`; `central_api/domains/suppliers/{models,schemas,repository,service,router,seed}.py`; `migrations/versions/…0003_suppliers_schema.py`; `services/central-api/scripts/import_suppliers_from_tinydb.py`; `services/central-api/tests/fixtures/sample-incidents.csv` (moved); `uis/backoffice/app/api/health/route.ts` (+ test); `docs/planning/{deployment-dockerization,supplier-directory-postgres-migration}.md`; `docs/runbooks/{backend-coolify-deployment,supabase-migrations,identity-tinydb-backup-restore}.md`; `docs/archive/{incident-report-processor-retirement,supplier-directory-retirement}.md`.

**Modify:** `uis/backoffice/next.config.ts` (`standalone`+`outputFileTracingRoot`); `uis/backoffice/lib/server/service-urls.ts` (suppliers→`CENTRAL_API_URL`; drop supplier/incident-processor URLs); `uis/backoffice/.env.example`; `central_api/main.py` (suppliers_router); `central_api/core/config.py` (`MIGRATION_DATABASE_URL`, `sslmode`, timeouts) + `db/session.py`; `migrations/env.py`; `central-api/pyproject.toml` (`seed-suppliers`); `central-api/README.md` + `central-api/tests/test_incidents.py` + `packages/trackflow_incidents/README.md` (fixture path); `identity/identity/cli.py` (revoke-sessions); `conftest.py` (drop incident_processor branch); `scripts/README.md`; `uis/website/` header; `.gitignore` audit; docs (`README.md` roadmap, `memory-bank/progress.md`, `docs/runbooks/README.md`, `.github/workflows/README.md`).

**Delete (retirement note + git history):** `services/incident-processor/` + `scripts/analyze.py` (now, after extraction); `services/supplier-directory/` (Phase 12).

**Leave untouched:** Vercel website deploy config; `packages/shared` (protected); `docs/briefs/*` & `docs/standards/*` (protected); archived planning docs' historical paths; original `suppliers.json` until rollback window closes.

---

## Verification (prove it end-to-end)
1. **Local:** `docker compose up` `/health` green; `--profile setup run migrate`→head; backoffice login (cookie) + create inventory order + incident + supplier (CSRF) persist; **unauthenticated GET `/api/health` returns 200 (not 307)**.
2. **Importer:** run against a copy → counts + field-level equality (incl. `has_contact_email`) vs source; supplier list/detail unchanged.
3. **Supabase (approval-gated):** `pg_dump` → migrate (DDL role) → seed inventory (DML, real UUID) + suppliers → central-api `/health` `database: ok` via runtime connection; **incidents empty**.
4. **Coolify prod:** HTTPS login sets `Secure; HttpOnly` cookies; CSRF + password reset work; internet `curl` to backend fails; only `backoffice.forgehub.cloud` serves; Traefik cert valid; website link works.
5. **DR drills:** restore Identity volume into a scratch container, run `revoke-sessions` + key rotation, confirm login; confirm Supabase restore path.

---

## Sources (current official docs)
- Supabase — Connecting to Postgres (direct/session/transaction, IPv4/IPv6): https://supabase.com/docs/guides/database/connecting-to-postgres
- Supabase — Supavisor terminology / FAQ: https://supabase.com/docs/guides/troubleshooting/supavisor-and-connection-terminology-explained-9pr_ZO · https://supabase.com/docs/guides/troubleshooting/supavisor-faq-YyP5tI
- Supabase — Disabling prepared statements: https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL
- Supabase — Backups / PITR: https://supabase.com/docs/guides/platform/backups
- Supabase — Roles / least-privilege: https://supabase.com/docs/guides/database/postgres/roles
- Coolify — Docker Compose + networking/ports: https://coolify.io/docs/knowledge-base/docker/compose · https://coolify.io/docs/builds/packs/docker-compose
- Coolify — Env vars & build secrets: https://deepwiki.com/coollabsio/coolify/5.3-environment-variables-and-build-secrets
- Coolify — Requirements / same-server build warning: https://coolify.io/docs/get-started/introduction
- Next.js — Standalone output + monorepo (`outputFileTracingRoot`): https://nextjs.org/docs/app/api-reference/config/next-config-js/output
- Next.js — Middleware matcher: https://nextjs.org/docs/app/api-reference/file-conventions/middleware
- Docker — Build context & `.dockerignore`: https://docs.docker.com/build/concepts/context/
- Vercel — Domains / DNS records: https://vercel.com/docs/projects/domains
