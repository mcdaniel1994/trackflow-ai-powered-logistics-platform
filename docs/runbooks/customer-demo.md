# Customer chat, history and careers demo

Engagement 11 implements three locally reviewable phases. Hosted rollout, public corpus indexing
and paid AI checks are separate owner-approved operations. Nothing in startup, builds or tests
indexes a corpus or calls a live model.

## Phase 1: Back Office naming and history

Deploy the compatible Central API and Back Office changes together through the existing deployment
procedure after approval. No new migration is required. `first_line_cx` and existing trace IDs stay
compatible. Session create/list/detail responses gain a derived `title`; list retrieval is one
owner-scoped query capped at 50 sessions (repository hard cap 100). Dates retain their secondary
place and latest-activity ordering. Check an existing, empty and new conversation after reload.
Titles never enter logs, traces or analytics.

## Phase 2: Careers and the shared talent sandbox

Set **the same** server-only `TALENT_API_URL` in Website and Back Office. Configure the website's
public `NEXT_PUBLIC_BACKOFFICE_URL` to the authenticated Back Office origin. Keep
`CAREERS_DEMO_ENABLED=false` until the live contract exercise below passes. There is no applicant
database, file upload, CV URL or personal profile field. All emails must end in `@example.com`;
acknowledgement of fictional information is required. The adapter supplies `+1-202-555-0100`.

The public [sandbox OpenAPI contract](https://playground.4geeks.com/tracker/api/v1/openapi.json)
was read on October 13, 2026, without reading applicant records or making writes. `POST /records`
accepts `full_name`, `email`, `phone`, `position`, `experience_years`, `linkedin_url`, and `cv_url`.
It documents a `201 RecordOut` response with string `id`, `status`, `stage`, and `applied_at`.
Create does **not** accept state/time controls. The sandbox owns these server-side defaults; the
website requires returned `received`/`pending` and a valid application timestamp before reporting
success. No undocumented fields or follow-up repair write are sent. The published schema alone does
not establish the defaults. The October 14 authorized live exercise confirmed them.

Before hosted enablement, perform one explicitly approved fictional write against the selected
sandbox. Verify confirmed `201` creation, `received`/`pending`, server timestamp, candidate detail,
stage update and note creation through the authenticated Back Office. Use a unique demo email,
never real applicant details. Check whether this shared third-party sandbox is suitable for the
demo and note its reset behavior. If contract/defaults differ, keep the flag off and adapt/test
the integration before enabling. Do not use real recruiting data.

Enable `CAREERS_DEMO_ENABLED=true` only in the website after that check. The form shows success only
for a confirmed record. It disables concurrent clicks. Timeout, network failure, malformed
confirmation or upstream 5xx yields an uncertain outcome and prevents a second submission in the
current form. Check the tracker before deciding to submit again; a timeout may have created a
record. Nothing automatically retries the write. Sandbox errors and applicant data are never logged.

## Phase 3: Public-only support

1. Review the explicitly curated [public corpus](../public-knowledge-base/README.md). It includes
   website FAQs and public delivery/returns passages, excluding private commercial terms and staff
   procedures. The application always targets the separate `trackflow_public` collection; see
   [Qdrant collections](https://qdrant.tech/documentation/manage-data/collections/).
2. After paid indexing approval, run `rag-index --public` in the Central API environment with
   the existing embedding key and Qdrant configuration. This entrypoint pins both corpus and
   collection and rejects a custom corpus or destructive recreation. Do not run it during a build
   or service startup. Inspect payloads for public-only content and country labels before enabling.
3. Supply one server-only `WEBSITE_GATEWAY_SECRET` through the existing secret management surface
   to Website, Back Office and Central API. Do not copy provider keys into either frontend.
   Set Website `SUPPORT_GATEWAY_URL` to the HTTPS Back Office origin; Back Office's existing
   `CENTRAL_API_URL` remains private. No browser cookies or Authorization header are forwarded.
4. Keep `PUBLIC_SUPPORT_ENABLED=false` in all three services until approved hosted verification.
   Missing flags, gateway credentials, provider credentials or public collection fail closed.
   After approval, enable all three flags and check grounded English/Spanish answers for US/Spain,
   follow-up context, private-data/action refusals, dependency failures and rate limits.
5. The UI retains transcript only in page memory and sends at most three completed exchanges
   totalling 6,000 characters. Language and policy selection are independent. Public history is
   untrusted conversational context; retrieved public passages supply factual claims. Answers are
   complete, with loading/error states; there is no public WebSocket, storage or operational tool.

Central API limits requests to two active, 30 per minute globally and 200 per UTC day before provider
calls. Counters are bounded, in memory, single process and reset on restart. **Run one worker and
one replica.** Restarting is not a quota-preserving operation. Scaling requires shared admission
state. The deadline is 30 seconds; vector/embedding calls are bounded at five seconds and generation
at 15 seconds, with SDK retries disabled. Timed-out work retains capacity until its I/O finishes.
Relay timeouts are 35/40 seconds and browser timeout 45 seconds. There are no automatic retries.

## Local verification

Use an isolated migrated PostgreSQL database on port 55432. Set `DATABASE_URL` to it; never run the
test cleanup against a deployed database. Run Central API and data suites sequentially because
both truncate disposable test tables. Override local feature flags/content-storage/model settings
for deterministic mocked tests:

```bash
AGENTS_ENABLED=false AGENTS_STORE_CONTENT=false RAG_ENABLED=false RFP_ENABLED=false \
PUBLIC_SUPPORT_ENABLED=false RAG_GENERATION_MODEL=deepseek-chat OPENAI_API_KEY='' DEEPSEEK_API_KEY='' \
uv run --project services/central-api pytest -c services/central-api/pyproject.toml \
  services/central-api/tests --cov=central_api --cov-report=term-missing
uv run --project data pytest -c data/pyproject.toml --cov=pipelines --cov=process
npm run test --workspace trackflow-backoffice
npm run test --workspace trackflow-website
npm exec --workspace trackflow-backoffice playwright test -- --config playwright.customer-demo.config.ts
```

The dedicated Playwright configuration starts Website on 3005 and Back Office on 3006, both
pointing at an ephemeral in-memory HTTP sandbox/Identity fixture on 18884. It exercises real
server routes, login cookie relay, application confirmation, candidate navigation, stage update,
note creation/reload, tracker refresh and the mobile public panel. It never uses live identities,
sandbox writes or AI calls. Do not run `next build` concurrently with this configuration: both
processes write the same app build directory. Lint, type-check, build, and Python coverage gates
must also pass for the two apps, Central API and data package.

The public page follows existing website locale behavior: English server-rendered content with
the client language toggle. Metadata, WebPage schema and sitemap include Careers; no fictional
`JobPosting` markup is emitted. Keyboard focus/dismissal and mobile overflow are browser-tested.
No new translated route structure or hosted performance/indexing result is claimed.

The October 14 preview correction keeps the launcher above the footer and compact on mobile.
English/Spanish greetings receive static welcome copy without an AI request or country selection;
they contain no policy answer. Disabled policy queries return `503 {code: "not_enabled"}` and the
panel explains that the demo's policy answers have not been enabled. Configuration or dependency
failures remain separate safe unavailable responses. No flag or credential was changed by this fix.

With the website preview running on `127.0.0.1:3005` and public AI disabled, run
`npm exec --workspace trackflow-backoffice playwright test -- --config playwright.support-layout.config.ts`
to verify footer links are unobstructed at mobile/desktop widths, the greeting works, and the
disabled policy message is clear. It creates no candidate records or paid AI calls.

## Rollback and unexecuted checks

Disable `PUBLIC_SUPPORT_ENABLED` in Website first, then gateway/API; disable
`CAREERS_DEMO_ENABLED` to stop intake. Existing staff chat and talent management remain available.
Leave sandbox records and collections intact. Roll back images through the established deployment
runbook if needed; there is no Engagement 11 database downgrade.

Hosted deployment, hosted accessibility/performance and search-engine indexing remain unexecuted.
Local public collection indexing, paid provider checks and live sandbox write/default verification
passed October 14 under the owner's explicit authorization.
Local release evidence is recorded in the [Engagement 11 specification](../planning/remaining_planning/spec-11-customer-demo.md).

## Owner-authorized local enablement — October 14

The owner delegated local configuration, indexing and live checks. The working preview is
`http://127.0.0.1:3005`; Careers is `/careers`, and Back Office is `http://127.0.0.1:3006`.
Runtime settings are in ignored, mode-0600 files, not `.env.example`:

- Website `uis/website/.env.local`: both demo flags enabled, local Back Office gateway/navigation
  origin, shared talent sandbox URL and server-only gateway credential.
- Back Office `uis/backoffice/.env`: public-support flag and credential, local Central API/Identity
  origins; talent URL matches Website.
- Central API `services/central-api/.env`: public-support flag and credential; existing provider
  keys stay here. The existing `gpt-4o-mini` model routes to OpenAI automatically. A diagnostic
  DeepSeek request returned HTTP 402; it is not the verified generation provider for this preview.

Isolated containers `trackflow-demo-postgres` and `trackflow-demo-qdrant` bind only localhost,
using same-named persistent Docker volumes. PostgreSQL is migrated to `20260820_0021`.
The Qdrant public collection contains 26 chunks from three curated documents: four US, four ES,
and 18 GLOBAL chunks. No internal collection was indexed. Existing local Identity data was reused.
No applicant database was introduced.

After stopping the preview, restart its containers with
`docker start trackflow-demo-postgres trackflow-demo-qdrant`. Start each stopped service in its
own terminal, checking for an already-running process first:

```bash
# From services/identity (Identity may already be running on 8002):
.venv/bin/uvicorn identity.main:app --env-file .env --host 127.0.0.1 --port 8002 --no-access-log
# From services/central-api:
.venv/bin/uvicorn central_api.main:app --host 127.0.0.1 --port 8003 --no-access-log
# From repository root, in separate terminals:
npm run dev --workspace trackflow-backoffice -- --hostname 127.0.0.1 --port 3006
npm run dev --workspace trackflow-website -- --hostname 127.0.0.1 --port 3005
```

Ordinary restarts do not require reindexing. When approved public documents change, run
`.venv/bin/python -m scripts.rag_index --public` from `services/central-api`; it makes paid embedding
calls. Do not recreate the collection or remove the Docker volumes as a routine restart.
Support admission counters reset when Central API restarts.

Live verification passed for US English delivery, Spain Spanish delivery, US Spanish returns,
follow-up express coverage, country clarification, private tracking redirect and injection refusal.
Desktop/mobile browser checks verified live answers, footer clearance and Escape/focus return.
One fictional application was confirmed with received/pending defaults and a server timestamp;
authenticated Back Office detail, stage `review` and a fictional note persisted after reload.
The retained demo candidate ID is `2fda39ca-0c91-4126-99fa-cadd01052147`; this shared sandbox can reset it.
No ambiguous application write was retried. Hosted deployment remains unexecuted.

### Demo admin privacy correction

The owner requested `admin@trackflow.com` instead of a personal email on the demo card. Both card
and autofill now use that address. The local demo Identity record was updated with Identity stopped,
after taking an ignored mode-0600 backup; its existing ID, password hash, permissions and history
ownership were preserved. Local browser sign-in with the alias opened the existing candidate.
No production Identity was changed. Before hosted rollout, update the corresponding demo admin email
through an approved Identity maintenance operation, preserve its ID, reject duplicate email aliases,
take a private backup and verify sign-in. Changing the UI alone does not change a stored login.
