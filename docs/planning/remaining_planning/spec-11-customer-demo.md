# Specification — Engagement 11: Customer Chat, History & Careers Demo

**Status:** owner approved October 13, 2026; all three local phases implemented and verified. Owner authorized local environment setup, paid public indexing/provider checks and fictional sandbox writes October 14; these checks passed. Hosted deployment remains unexecuted and separately gated.
**Brief:** [11-customer-demo](../../briefs/11-customer-demo.md).

## Phase 1 — Employee assistant

Use TrackFlow Assistant and “Ask about company policies and support tickets.” Preserve technical IDs. Add response-only title derived from the first persisted user message: collapse whitespace, truncate at a word boundary within 60 characters, ellipsis if truncated; empty title New conversation. Bounded owner-scoped queries, no schema migration or per-session transcript reads. Desktop/mobile history leads with title and keeps date secondary; provisional titles reconcile with persistence and failures. No title content in telemetry.

## Phase 2 — Careers demo

Bilingual /careers linked from footer, illustrative Executive Assistant—Zaragoza, Warehouse Associate—Los Angeles, Customer Support Specialist—Zaragoza and General application. Apply selects role. Form collects fictional name, example.com email, role, experience and demo acknowledgement, with sample fill. No uploads, personal URLs or real phone; sandbox phone uses a fictional constant, URL fields empty. Same-origin validated server submission creates received/pending record with UTC server time in existing TALENT_API_URL sandbox. Confirmed creation returns only candidate ID; authenticated back-office link. Disable concurrent submits, never auto-retry writes, explain ambiguous timeout. Generic Talent Pipeline heading and explicit Refresh. Metadata/sitemap/WebPage schema, never fictional JobPosting markup.

## Phase 3 — Public support

Site-wide accessible bilingual panel, TrackFlow Support. Separate policy-country selection from language. Anonymous public policies only; private ticket/shipment/actions redirect to contact. In-page transcript only, complete responses, no WebSocket or persisted guest history. Previous three exchanges maximum, untrusted and bounded at 6000 characters; question 1000 characters. Reuse retrieval/generation/guardrails in a knowledge-only path with no MCP, memory or staff principal. Curated public corpus indexed into trackflow_public, fail closed on missing collection/configuration.

POST /api/support/query on website → fixed server-authenticated Back Office gateway → private POST /public-support/query. No cookies or broad proxy; server-only secrets. Thirty-second backend deadline, bounded provider I/O, no automatic retries. Admission limits before provider calls: two concurrent, 30/min globally and 200/UTC day; bounded single-process in-memory counters reset on restart. Independent feature flag off by default. No raw chunks or traces in responses. Safe unavailable/timeout handling.

## Verification and release

Mock providers/sandbox in tests; test owner isolation/titles, guardrails/grounding/country/language/context/limits/dependencies, careers validation/write outcomes and full synthetic application→login→record→stage→note journey. Lint/type-check/build/tests/coverage for all touched packages and apps. Public accessibility and visibility sections 1–6, auth, database, telemetry and engineering-quality standards apply. Live sandbox contract verification required before hosted enablement; hosted deployment and paid AI calls remain separately approved. No real applicant or customer data.

## Implementation contract clarification

The live sandbox's public OpenAPI schema was read without record access or writes on October 13.
`RecordCreate` accepts applicant fields only; state and time controls are absent. The adapter sends
only those documented fields and confirms the sandbox-owned `received`/`pending` defaults and valid
server `applied_at` in its response. Unexpected state/time, malformed confirmation, upstream 5xx or
write timeout produces an uncertain outcome and no automatic retry. Live creation/default behavior was verified against the configured sandbox on October 14,
including authenticated candidate detail, persisted stage update and note.

## Reviewable phases

| Phase | Main review surfaces |
|---|---|
| 1 — employee naming/history | Central API `domains/chat/{schemas,repository,service}.py`; Back Office `ChatPanel`, `AskKnowledgeBox`, agent types and history tests |
| 2 — careers integration | Website `app/careers`, `components/careers`, `lib/careers`, `api/careers/applications`; Talent Pipeline heading/Refresh; mock cross-app browser journey |
| 3 — public support | Website `components/support` and `api/support/query`; fixed Back Office `api/public-support/query`; Central API `domains/public_support`; opt-in RAG options, public corpus and index entrypoint |

## Local release evidence

Verified on October 13, 2026 against an isolated PostgreSQL 17 database migrated through existing
head `20260820_0021`. No Engagement 11 migration or applicant database was introduced.

| Target | Result |
|---|---|
| Central API | 502 tests passing; 91.41% branch-aware coverage (90% gate); Ruff, strict mypy (109 files), wheel/sdist build passing |
| Data pipelines | 146 tests passing, one opt-in performance test skipped; 92.16% branch-aware coverage (90% gate); Ruff, strict mypy (24 files), wheel/sdist build passing |
| Back Office | 202 unit/component tests passing; lint, type-check and production build passing |
| Website | 27 unit/component/route tests passing; lint, type-check and production build passing |
| Browser journey | Two Chromium checks passing: fictional submission → login cookie relay → same record → stage update → note/reload → tracker Refresh; mobile panel focus/Escape, safe disabled response, bilingual careers and horizontal overflow |
| Configuration/scope | Both Compose files validate with dummy environment values; `git diff --check` passes; no delivered brief/archive/visibility-standard/shared-package changes |

Providers, Qdrant, talent writes and Identity are mocked in automated tests. Public corpus boundaries,
fixed retrieval target/country, input/history/evidence/output rejection, language selection, missing
configuration/collection, limits, dependency failures and deadline capacity are covered. History
tests include empty/existing/long/multiline/Spanish labels, owner isolation, one-query list retrieval,
desktop/mobile labels and provisional failure reconciliation. Careers checks cover strict fields,
demo emails, acknowledgement, sample/role selection, confirmation, duplicate pending clicks and
ambiguous writes. Logs emit no application, title, question, answer or provider exception content.

Desktop Careers, Spanish mobile Careers and mobile Support screenshots were visually inspected.
Careers has server-rendered primary content, semantic roles/form labels, metadata, WebPage schema
and sitemap entry; no JobPosting schema. It inherits the site's existing English SSR/client locale
toggle without new translated routes. Hosted accessibility, performance and indexing are not claimed.

Rollout, flags, credential placement, counters resetting on restart, the published sandbox contract,
remaining live checks and rollback are recorded in [the runbook](../../runbooks/customer-demo.md).

## October 14 preview corrections

Owner-reported defects: the fixed launcher covered Careers/Privacy/LinkedIn at the footer, and
"Hello" yielded an unavailable response because the live policy service remained off.
The launcher now clears the visible footer with a compact, accessibly named mobile icon. Its
offset follows scroll, viewport changes and content resizing. Greetings receive a static
English/Spanish welcome without a country selection or AI call; policy requests still require
country and backend configuration. A disabled feature reports "not enabled" rather than a
temporary outage. No flag, provider credential, public index or hosted deployment was changed.

Regression tests failed for both reported defects before the fix. Website's updated suite has
32 passing tests. Two additional browser regressions verify mobile/desktop launcher geometry and
actual footer link hit targets on home/careers, greeting response, disabled policy feedback and
focus return. The existing two cross-app browser checks continue to apply. Website and Back Office
lint, type checks and builds pass for this correction, along with 202 Back Office unit tests and
all four dedicated browser checks. Python production code is untouched.

## October 14 authorized local live verification

Owner delegated remaining local setup and live exercises. Ignored local environment files now
enable Careers and public support, with a fixed localhost gateway and one server-only credential.
Existing provider keys remain in Central API; the original OpenAI `gpt-4o-mini` model is verified.
DeepSeek returned HTTP 402 during diagnosis; no billing change or new key was made.

Public indexing completed: three curated documents, 26 chunks in `trackflow_public` (US 4, ES 4,
GLOBAL 18). US English and Spain Spanish delivery, US Spanish returns and a grounded follow-up
returned answers through the website. Missing country clarified; tracking redirected; injection
was refused. Two live browser checks passed for mobile/desktop footer clearance, policy response,
Escape dismissal and focus return. These paid/manual checks supplement mocked automated tests.

One unique fictional sample was created through Careers with confirmed received/pending/server
timestamp. Its authenticated Back Office detail loaded; a stage update to review and demo note
persisted after reload. Initial automated demo-login navigation timed out; completing login with
the published demo credentials succeeded without repeating the application write.
Container storage preserves the local public index across restarts. No hosted deployment,
production database mutation or hosted search-engine indexing occurred. See the runbook for
local restart instructions and the retained fictional candidate ID.

The October 14 owner privacy correction changes Admin Demo display/autofill to `admin@trackflow.com`.
The local demo account email was changed with a private backup and Identity stopped; account ID,
password and history ownership remain intact. Browser sign-in with the alias passed. Hosted Identity
requires the corresponding approved maintenance step before rollout; no production account changed.

Privacy correction verification: all 202 Back Office tests, lint, type-check and production build
passed. Existing login/autofill assertions now use the demo alias; the live browser login passed.
No commit, push or hosted account change was performed.
