# Specification — Final Polish: Public Website + Back Office

**Status:** Proposed. Owner-requested 2026-08-19, pending owner approval.
**Implementer:** Codex.
**Scope:** Two phases. Phase 1 — public website. Phase 2 — Back Office.
**Context:** Engagement 10 is merged to `main`. This is the pre-recording, pre-submission polish pass.
It is not a new engagement; it is corrective and presentational work across delivered surfaces.

---

## 0. How to use this document

Every item below states **Current behavior** (verified against the running stack and live database on
2026-08-19, not assumed), **Expected behavior**, **Files**, **Implementation**, **Acceptance criteria**,
and **Tests**. Do not re-derive the diagnosis; it is recorded here because several root causes are
non-obvious.

### 0.1 Mandatory reading before touching code

Per `AGENTS.md` and `CLAUDE.md`, apply the scoped rules whose file patterns you touch:

| Touching | Apply |
|---|---|
| `uis/website/**` | `.agents/rules/public-ui-visibility.md` → `docs/standards/visibility.md` §1–6 |
| Telemetry fields, trace content, retention | `.agents/rules/telemetry.md` → `docs/standards/telemetry-standard.md` |
| Any behavior/validation/failure path/CI | `.agents/rules/testing-error-handling-ci.md` + `docs/standards/` |
| Any new/changed dependency or model/provider | `.agents/rules/compliance-licensing.md` |
| Auth/session/cookie/authorization surfaces | `.agents/rules/authentication-security.md` |

### 0.2 Non-negotiables carried from existing decisions

- **No new runtime dependency** is added by this spec. `uis/backoffice` dependencies are currently
  exactly `@repo/shared-types`, `lucide-react`, `next`, `react`, `react-dom`. Charts are hand-rolled
  inline SVG (§2.3). Adding a charting library or a PDF writer is a separate owner decision under the
  compliance-licensing rule.
- **Raw PDF bytes are never persisted** (Engagement 9 owner decision). §2.2 does not change this.
- **Guardrail-blocked content is never stored** (telemetry standard §8). §2.1 preserves this.
- Follow the **Mandatory Pre-Commit Workflow** in `AGENTS.md` §"Mandatory Pre-Commit Workflow".

### 0.3 Owner decisions required before Phase 2 starts

Three items in this spec cannot be resolved from the code. They are flagged inline and repeated here:

| # | Decision | Recommendation |
|---|---|---|
| D1 | §2.1 — enable `AGENTS_STORE_CONTENT` and store truncated prompt/answer previews for chat-session runs | Approve. It is the existing sanctioned opt-in, and Engagement 10 already persists full chat content under an approved exception. |
| D2 | §2.3 — the premise "Run now / Force refresh are dead because Prefect is unused" is **factually incorrect** (see §2.3.1) | Still remove both buttons, but as a product/demo choice, not a correctness fix. Keep the Central API endpoint. |
| D3 | §2.5 — removing the top toggle orphans `TechnicalOverview` | Give it its own sidebar route rather than deleting it. |

---

## PHASE 1 — Public Website

Files are all under `uis/website/`. Both items are presentational and share the header; do them together.

### 1.1 Mobile navigation → top dropdown

**Current behavior.** `components/layout/MobileNav.tsx` renders a **fixed bottom bar**
(`fixed bottom-0 left-0 right-0 z-50 grid grid-cols-6 … md:hidden`) with six links: Home, Services,
Coverage, Contact, Apply, Login. It is mounted in `app/layout.tsx:46`, and `app/layout.tsx:40` compensates
with `<body className="pb-12 md:pb-0">`. `components/layout/SiteHeader.tsx` renders the desktop nav
(`hidden … md:flex`) and hides the Login pill below `md`, so on mobile the header carries only the
wordmark and the language toggle.

**Expected behavior.** No bottom bar. The header carries a hamburger disclosure button on mobile that
opens a polished dropdown panel containing the same six destinations. Desktop is unchanged.

**Files.**
- `uis/website/components/layout/SiteHeader.tsx` — add the disclosure button + panel.
- `uis/website/components/layout/MobileNav.tsx` — **delete**.
- `uis/website/app/layout.tsx` — remove the `MobileNav` import and render; change `<body className="pb-12 md:pb-0">` to remove the bottom padding.
- `uis/website/tests/navigation.test.tsx` — update (it currently renders `<MobileNav />` directly).

**Implementation.**
1. `SiteHeader` is already `"use client"`. Add `const [menuOpen, setMenuOpen] = useState(false)`.
2. Render a trigger button, visible only below `md` (`md:hidden`), with `aria-expanded={menuOpen}`,
   `aria-controls="mobile-site-menu"`, and an `aria-label` that reflects state (Open/Close navigation).
   Use `lucide-react` `Menu` / `X` — already a dependency of the website? **Verify first**; if
   `lucide-react` is not in `uis/website/package.json`, draw the icon as inline SVG with
   `aria-hidden="true"` rather than adding a dependency.
3. The panel (`id="mobile-site-menu"`) renders below the header bar as a `<nav aria-label="Mobile navigation">`
   containing a `<ul>` of the six items — the same six the deleted `MobileNav` had, including
   `apply` and `login` and the `getBackOfficeURL()` destination, reusing the existing `homeHref(pathname, hash)`
   helper so in-page anchors keep working from `/application` and `/privacy`.
4. Behavior: close on item click (so hash navigation is visible), close on `Escape`, close on
   `pathname` change, and return focus to the trigger on close. Render a backdrop that closes on click.
5. Sizing/polish: each row ≥ 44px tall, full-width tap target, the existing type scale
   (`text-sm font-semibold text-neutral-700`), `hover:text-coral` to match desktop, `border-mist`
   dividers, and the header's existing `bg-white/95 backdrop-blur` treatment so it reads as one surface.
6. Keep `LanguageToggle` in the header bar itself (outside the panel) — it must stay reachable while the
   menu is closed.

**Accessibility (from `docs/standards/visibility.md`, mandatory).** Native `<button>` and `<nav>`/`<ul>`/`<li>`
— no ARIA menu roles (a nav disclosure is not a `role="menu"`). Only `aria-expanded`/`aria-controls`
plus `aria-hidden` on decorative icons. Keyboard reachable and operable. Contrast ≥ 4.5:1 on body text.

**Acceptance criteria.**
- No fixed bottom navigation exists anywhere on the site at any viewport.
- At < 768px the header shows a hamburger; activating it reveals all six destinations; activating it
  again (or Escape, or backdrop, or choosing an item) closes it.
- At ≥ 768px the header is visually and behaviorally identical to today; no hamburger is rendered.
- `<body>` no longer reserves bottom padding.
- Focus returns to the trigger after close; the panel is keyboard-navigable.
- One `<h1>` per page, `<html lang>`, canonical, OG/Twitter metadata and JSON-LD remain intact.

**Tests** (`uis/website/tests/navigation.test.tsx`, vitest + testing-library).
- Replace the `renders <MobileNav />` test with one that renders `<SiteHeader />`, activates the
  hamburger, and asserts the Login link inside the mobile nav resolves to the configured Back Office URL
  (preserving the existing assertion's intent).
- Assert `aria-expanded` flips false→true→false.
- Assert Escape closes the panel.
- Keep the existing desktop-header Login assertion unchanged.

---

### 1.2 Hero image → looping background video

**Current behavior.** `components/sections/Hero.tsx` renders `next/image` with
`src="/images/trackflow-operations-hero.png"`, `fill`, `priority`, `sizes="100vw"`, `className="object-cover"`,
`alt={copy.imageAlt}`, followed by **two** overlay divs that create the tint:

```
bg-gradient-to-r from-navy-deep/95 via-navy-deep/80 to-navy-deep/20
bg-gradient-to-b from-navy-deep/20 via-transparent to-navy-deep/30 lg:w-3/5
```

Copy (`headlineLead` + coral `headlineHighlight`, `subheading`, CTA) sits above them with
`drop-shadow-[…] hero-copy-shadow`.

**Asset.** `uis/website/public/images/trackflow_video.mp4` — 1.41 MB, ~10 s, currently **untracked**
(`git status` shows `??`) and **not** gitignored. It will be committed with this change.

**Expected behavior.** The video replaces the still as the hero background: autoplaying, looping,
silent, seamlessly integrated. Tint, headline weight/copy, layout, and CTA are **unchanged**.

**Files.** `uis/website/components/sections/Hero.tsx` only. Do **not** delete
`public/images/trackflow-operations-hero.png` — `content/schema.ts:10,30` uses it for JSON-LD
`image`/`logo`, and it becomes the video poster.

**Implementation.**
1. Replace the `<Image>` element with a `<video>` positioned identically:
   `className="absolute inset-0 h-full w-full object-cover"`.
2. Attributes: `autoPlay`, `loop`, `muted`, `playsInline`, `preload="metadata"`,
   `poster="/images/trackflow-operations-hero.png"`.
   - `muted` is **required** — browsers block autoplay with sound.
   - `playsInline` is **required** — iOS Safari otherwise forces fullscreen playback.
   - The poster preserves the current first paint and the LCP candidate while the video loads.
3. Source: `<source src="/images/trackflow_video.mp4" type="video/mp4" />`.
4. The video is **decorative** — the headline and subheading carry all meaning. Mark it
   `aria-hidden="true"` and `tabIndex={-1}` so it is not announced and not a tab stop. This is exactly
   the "aria-hidden on decoration" case the public-UI rule calls for. `copy.imageAlt` stays in the
   content files and is used as the poster fallback's alt text (step 5) — do not delete the key from
   `site.en.ts` / `site.es.ts`.
5. **Reduced motion is mandatory, not optional.** The clip loops indefinitely, so it is moving content
   longer than 5 seconds (WCAG 2.2.2). Under `prefers-reduced-motion: reduce`, do not play it: render
   the still instead. Prefer a CSS-only solution so it holds without JS — e.g. in `app/globals.css`:

   ```css
   @media (prefers-reduced-motion: reduce) {
     .hero-video { display: none; }
     .hero-video-fallback { display: block; }
   }
   ```

   with `.hero-video-fallback { display: none; }` by default, the fallback being an `<img>` (or
   `next/image`) using the same poster and `alt={copy.imageAlt}`.
6. Keep **both** overlay gradient divs byte-identical and in the same order — they are the tint
   treatment the owner asked to preserve. Keep the copy block, its `drop-shadow`/`hero-copy-shadow`
   classes, the coral `headlineHighlight` span, and the CTA exactly as they are.
7. Keep `min-h-[76vh]` and `overflow-hidden` on the section.

**Acceptance criteria.**
- The hero plays the video automatically, silently, on loop, on desktop and mobile (verify iOS Safari
  behavior via `playsInline`).
- The tint, headline (including bold weight and coral highlight), subheading, and CTA are visually
  unchanged from the current hero.
- With `prefers-reduced-motion: reduce`, no video plays and the still is shown instead.
- No layout shift versus the current hero; the poster covers the first paint.
- JSON-LD still references the PNG and still parses.
- No console errors; the mp4 is committed.

**Tests.**
- `uis/website` has vitest only (no Playwright). Add a render test asserting the `<video>` carries
  `autoplay`, `loop`, `muted`, `playsinline`, and a `poster`, and that the two gradient overlay
  elements are still present.
- Manual: confirm playback in the running site at mobile and desktop widths, and confirm the
  reduced-motion path via the OS/browser setting or emulation.

---

## PHASE 2 — Back Office

All files under `uis/backoffice/` and `services/central-api/` unless noted.

### 2.1 Agent OS telemetry — latency, tokens, cost, tools, output preview

**This is a data-production problem, not a rendering problem.** `components/agents/AgentOSDashboard.tsx`
already renders every field and correctly falls back to `—` when a value is null
(`duration()` L33, `cost()` L38, `Metric` rows L89–91, per-step L110–112, tool list L125–129, output
preview L138). **Do not "fix" the dashboard first.**

**Current behavior — verified against the live trace store (12 runs):**

| Symptom | Verified evidence |
|---|---|
| Tokens/cost blank on RFP runs | `trackflow-rfp-intake`, `-generation`, `-approval` rows: `total_tokens` and `total_cost_usd` NULL; 0 of their 11 node steps have tokens |
| Tokens present but cost blank on some CX steps | `trackflow-cx-agent`: 56 steps, 15 with tokens, only 7 with cost |
| Output/input preview always empty | `SELECT count(input_summary), count(output_summary) FROM agent_runs` → **0 and 0**, across all 12 runs |
| Latency zero on approval runs | both `trackflow-rfp-approval` rows have `duration_ms = 0` |
| Tools used | **Working** — `agent_tool_calls` holds `ticket_status` rows for the CX agent |

**Root causes.**

- **(A) Output/input preview.** `domains/agents/service.py:198` `_summaries()` returns `(None, None)`
  whenever `settings.agents_store_content` is false, and `core/config.py:78` defaults it to `False`.
  Additionally `service.py:132–135` forces `(None, None)` whenever `chat_session is not None` **or** any
  guardrail event fired. Since Engagement 10 routes every Ask-AI turn through a chat session, that
  branch alone guarantees a permanently empty preview even if the setting were enabled.
- **(B) RFP steps never carry usage.** `domains/rfp/generation.py:209–226` `_step()` hardcodes
  `"tokens": None, "cost_usd": None`; `intake.py` and `approval.py` build steps the same way and call
  `persist_run(..., input_summary=None, output_summary=None)`.
- **(C) RFP intake discards usage at the call site.** `domains/rfp/agents.py:105–116`
  `_invoke_structured()` calls `llm.with_structured_output(schema).invoke(...)`, which returns the parsed
  Pydantic object. The underlying `AIMessage` — and therefore `usage_metadata` — is thrown away.
- **(D) RFP drafting discards usage.** `domains/rfp/generation.py:115` calls `pipelines.rag.complete()`,
  and `data/pipelines/rag.py:497` declares `complete(...) -> str`. It returns a bare string, unlike
  `generate_answer()` which returns a `GenerationResult` carrying `usage`.
- **(E) DeepSeek has no price entry.** `domains/agents/pricing.py` `MODEL_PRICES` contains only
  `gpt-4o-mini` / `gpt-4o-mini-2024-07-18`. `_build_usage()` deliberately returns `cost=None` for unknown
  models rather than fabricating a number. `deepseek-chat` generation steps therefore produce exact
  tokens with no cost — by design, which is why 15 steps have tokens but 7 have cost.
- **(F) Approval latency.** `domains/rfp/approval.py:288` sets `duration_ms=0` literally when building
  the `AgentRunResult`, unlike `generation.py:236` which sums step durations.

**Expected behavior.** Every Agent OS run shows real latency, token usage, tools used, and a final-output
preview. Cost is shown wherever the model is priced, and is explicitly labeled "not priced" — never
silently blank — where it is not.

**Implementation.**

1. **(F) Fix approval latency.** In `domains/rfp/approval.py:_record_trace`, replace `duration_ms=0` with
   the sum of step durations, matching `generation.py`:
   `duration_ms=sum(int(step.get("duration_ms") or 0) for step in steps)`.

2. **(D) Return usage from the drafting primitive.** In `data/pipelines/rag.py`, add
   `complete_with_usage(system_prompt, user_content, config) -> GenerationResult` containing the existing
   `complete()` body but returning `GenerationResult(answer, None, _usage_counters(completion))` — reusing
   the existing `_usage_counters()` helper. Keep `complete()` as a thin wrapper returning `.answer` so no
   existing caller breaks. Do not change `generate_answer()` or `query()`.

3. **(B/D) Thread usage through RFP generation.** In `domains/rfp/generation.py`:
   - Call `complete_with_usage()` at L115 and keep the returned counters.
   - Extend `_step()` with optional `tokens`/`cost_usd` parameters (default `None`) instead of hardcoding.
   - Price the counters with the existing `usage_from_counters(counters, settings.rag_generation_model)`
     from `domains/agents/pricing.py` and attach to the generation step. The generator/evaluator loop can
     run multiple iterations — **sum** tokens across iterations for the step, and sum costs only when every
     contributing call was priced (otherwise leave cost `None`; never partially sum).

4. **(C) Capture usage in RFP intake.** In `domains/rfp/agents.py:_invoke_structured`, switch to
   `llm.with_structured_output(schema, include_raw=True)`. LangChain then returns a mapping with
   `raw` (the `AIMessage`), `parsed`, and `parsing_error`. Validate `parsing_error` is falsy and `parsed`
   is an instance of `schema` (preserving the current `RfpAgentError` behavior and messages), then derive
   usage with the existing `usage_from_message(raw, config.model)`. Return both parsed result and usage;
   update the four call sites (`classify_document`, `extract_metadata`, `extract_key_aspects`, and any
   other `_invoke_structured` caller) and record usage onto the matching step in `intake.py`.
   `rfp_model` defaults to `gpt-4o-mini` (`core/config.py:83`), which **is** priced — so intake gains both
   tokens and cost.

5. **(E) DeepSeek pricing — conditional.** Adding a price is a provider/pricing claim and therefore falls
   under `.agents/rules/compliance-licensing.md`.
   - **If** current DeepSeek `deepseek-chat` published rates can be verified from official documentation,
     add a `MODEL_PRICES` entry following the existing docstring convention in `pricing.py` — explicit
     USD-per-million input/cached-input/output values, with the source URL and the verification date in
     the docstring, exactly as the `gpt-4o-mini` entry does.
   - **If not**, change nothing in `pricing.py`. The `cost=None` behavior is correct and deliberate.
   - Either way, do **not** infer a price from the model name.

6. **(A) Restore the output preview.** Requires **decision D1**.
   - Set `AGENTS_STORE_CONTENT=true` for local and production configuration (`services/central-api/.env`
     and `compose.coolify.yaml`, alongside the existing `AGENTS_ENABLED`/`RFP_ENABLED` wiring). Keep the
     code default `False`.
   - In `service.py:132–135`, **remove the `chat_session is not None` suppression** but **keep the
     guardrail suppression**. Rationale to record in the code comment: Engagement 10 already persists full
     chat message content in `chat_messages` under the approved telemetry exception, so a truncated
     preview of the same content adds no new category of stored data; guardrail-blocked content remains
     unstored per telemetry standard §8.
   - Keep truncation at `_SUMMARY_MAX_CHARS` and keep the previews out of logs.
   - RFP flows may keep `input_summary=None` (their input is an uploaded client document, not a prompt),
     but **should** set `output_summary` on the approval/finalize run to a truncated consolidated-document
     preview, so completed RFP runs are not blank in the dashboard.

7. **UI honesty (`components/agents/AgentOSDashboard.tsx`).** Distinguish "no data" from "not priced".
   Where tokens exist but cost is null, render `Not priced` (with a title/tooltip naming the model) rather
   than `—`. Leave the existing "Content preview is disabled or unavailable for this run." fallback for
   genuinely empty previews.

**Acceptance criteria.**
- A new CX agent run shows non-zero latency, non-zero tokens, a cost value (routing model is priced), the
  tools it used when it took the ticket route, and a non-empty final-output preview.
- A new RFP upload produces `trackflow-rfp-intake` and `trackflow-rfp-generation` runs with non-null
  `total_tokens`; intake also has non-null `total_cost_usd`.
- A completed RFP approval run reports non-zero `duration_ms` and a non-empty output preview.
- Cost renders as `Not priced` (not `—`) wherever tokens exist but the model is unpriced.
- Guardrail-triggered runs still store **no** input/output summary.
- No prompt, completion, retrieved chunk, tool argument, or credential is written to logs.

**Tests** (`services/central-api/tests/`, pytest).
- `pricing`: `usage_from_counters` prices a `gpt-4o-mini` payload and returns `cost=None` for an unknown
  model (extend existing coverage if present).
- `rag`: `complete_with_usage` returns counters; `complete` still returns a plain `str` (regression guard
  for existing callers).
- `rfp` intake: with a stubbed LLM returning `{"raw": AIMessage(usage_metadata=…), "parsed": …}`, the
  persisted run has non-null `total_tokens`; a `parsing_error` still raises `RfpAgentError`.
- `rfp` generation: a stubbed `complete_with_usage` produces a step carrying tokens; multi-iteration loops
  sum tokens and leave cost `None` when any call was unpriced.
- `rfp` approval: `duration_ms` equals the summed step durations, not 0.
- `agents` service: with `agents_store_content=True`, a chat-session run **does** persist a truncated
  output summary; a guardrail-triggered run does **not**.
- Note the pre-existing trap recorded in project notes: the full central-api pytest suite truncates the
  local database via the `clean_database` autouse fixture, and `get_settings()` reads
  `services/central-api/.env` from disk. Move that `.env` aside for CI-parity runs, then restore it.

---

### 2.2 RFP final document — generate, store, download

**Current behavior.**
- On full approval, `domains/rfp/approval.py:_maybe_finalize` builds
  `consolidated = {section.department_id: section.draft_content or ""}` and persists one
  `RfpFinalDocument` row (`models.py:134`) holding `sections` (JSON), `currency`, `generated_at`.
  Ticket status becomes `done`.
- `GET /rfp/tickets/{id}/document` (`router.py:87`) returns that as JSON via `RfpFinalDocumentRead`
  (`schemas.py:67`).
- `uis/backoffice/lib/rfp/api.ts:53` **already implements `getDocument()`**, and the BFF
  `app/api/rfp/[[...path]]/route.ts:18` **already allowlists** the `document` path.
- **Nothing in the UI ever calls it.** `grep` for `getDocument` across `uis/backoffice` returns only the
  api/types definitions. `components/agents/RfpDesk.tsx:89–93` renders the banner *"Proposal complete —
  every department approved. The final document is ready."* with no link, no preview, and no download.

So the document exists as data, has an endpoint and a client function, and has **no user-reachable surface**.

**Expected behavior.** When a ticket reaches `done`, the operator can read the consolidated proposal in the
RFP Desk and download it as a file.

**Design decision — format.** Deliver **Markdown**. Section drafts are already Markdown, the renderer is
deterministic and unit-testable, and it adds **no dependency**. A real PDF writer (ReportLab/WeasyPrint)
is a new runtime dependency and a compliance-licensing decision; if the owner wants PDF, satisfy it with a
print-optimized view and the browser's "Save as PDF" rather than a new package.

**Files.**
- `services/central-api/central_api/domains/rfp/render.py` — **new**, deterministic Markdown renderer.
- `services/central-api/central_api/domains/rfp/router.py` — new download route.
- `services/central-api/central_api/domains/rfp/service.py` — new service method.
- `uis/backoffice/app/api/rfp/[[...path]]/route.ts` — extend the allowlist.
- `uis/backoffice/lib/rfp/api.ts` — add the download call.
- `uis/backoffice/components/agents/RfpDesk.tsx` — render the document + download control.

**Implementation.**

1. **Renderer** (`render.py`). Pure function, no LLM, no I/O:
   `render_final_document(ticket, document, sections) -> str`. Output structure:
   - `# RFP Proposal — <client name or ticket reference>`
   - A metadata block: client country, currency, monthly volume, deadline, generated timestamp (ISO, UTC),
     and the ticket id.
   - One `## <Department display name>` section per department, in a **fixed, deterministic order** (define
     an explicit ordering constant — do not rely on dict insertion or DB row order), each followed by its
     approved `draft_content`, and its approver/approved-at attribution where available.
   - A closing note that every section was human-approved.
   Escape/normalize nothing that would corrupt the drafts; they are already Markdown.
2. **Service.** `get_document_markdown(ticket_id, owner_user_uuid) -> tuple[str, str]` returning
   `(markdown, filename)`. Reuse the exact ownership and readiness checks already in `get_document`
   (`service.py:169–177`): 404 `"RFP ticket not found."` for a non-owned/missing ticket, 404
   `"The final document is not ready yet."` when no document row exists. Filename:
   `trackflow-rfp-<short-ticket-id>-<YYYYMMDD>.md`.
3. **Route.** `GET /rfp/tickets/{ticket_id}/document/download`, same `current_principal` dependency and
   `_require_enabled()` gate as the sibling routes. Return a `Response` with
   `media_type="text/markdown; charset=utf-8"` and
   `Content-Disposition: attachment; filename="<filename>"`. The filename is server-generated from a UUID
   and a date — never from client input.
4. **BFF.** In `isAllowed`, add the 4-segment case: `path.length === 4 && path[0] === "tickets" &&
   UUID_RE.test(path[1]) && path[2] === "document" && path[3] === "download"`, GET only. Confirm
   `lib/server/proxy.ts` relays `Content-Disposition` — `HOP_BY_HOP_HEADERS` does not include it, so
   `copyResponseHeaders` passes it through; add a test rather than assuming.
5. **Client.** `downloadDocument(ticketId)` in `lib/rfp/api.ts` using the existing `fetchWithAuth`
   pattern; read the response as a `Blob`, create an object URL, trigger an anchor click, then
   **revoke the object URL**. Surface failures through the existing `rfpError` mapping.
6. **UI** (`RfpDesk.tsx`). When `ticket.status === "done"`:
   - Fetch the document via the existing `getDocument()` and render the consolidated proposal — one
     collapsible block per department (`<details>`/`<summary>` is sufficient and native).
   - Replace the bare banner with the same message plus a primary **Download proposal (.md)** button.
   - Handle the loading state and the 404-not-ready case without breaking the rest of the ticket view.

**Acceptance criteria.**
- Approving the last outstanding department makes the proposal readable in the RFP Desk without a page
  reload beyond the existing refresh behavior.
- The Download button saves a `.md` file whose content matches the on-screen proposal.
- Department order in the file is deterministic across repeated downloads of the same ticket.
- A ticket that is not `done` returns 404 and the UI shows no download affordance.
- A ticket owned by another user returns 404 — never another owner's document.
- Raw PDF bytes are still never persisted.

**Tests.**
- pytest: `render_final_document` snapshot for a two-department ticket, including fixed ordering and the
  metadata block; download route returns the right media type, `Content-Disposition`, and 404s for
  not-ready and non-owned tickets.
- vitest (`uis/backoffice/tests/`): BFF allowlist accepts `.../document/download` and rejects
  `.../document/other` and non-UUID ids; `Content-Disposition` survives the proxy; `RfpDesk` renders the
  download control only for `status === "done"`.

---

### 2.3 Business Reporting — controls and visualization

#### 2.3.1 Correction to the premise (decision D2)

The request says the Run Now / Force Refresh controls are unnecessary "since we are not using Prefect in
Coolify." **That premise does not hold, and the buttons are not dead.** Verified:

- `compose.coolify.yaml` deploys **`reporting-worker`** with `REPORTING_EXECUTOR: direct_sql` (L361).
- It also still deploys `prefect-server`, `prefect-postgres`, `prefect-postgres-bootstrap`,
  `prefect-postgres-guard`, `prefect-version-guard`, and `prefect-db-backup`. **Prefect is still deployed
  in Coolify**, contrary to the premise.
- `docs/runbooks/business-performance-pipeline.md` states production selects `direct_sql`, and that
  **"final Prefect removal remains separately owner-gated."**
- The buttons `POST /reporting/pipeline-runs`, which enqueues into the `reporting.pipeline_runs`
  PostgreSQL queue that `reporting-worker` drains. **Prefect is not in that path at all** in direct-SQL
  mode. So the controls still perform real, working refreshes in production today.
- "Load week" is unrelated — it re-queries an already-published week and never enqueues work.

Therefore removing these buttons is a **product/demo decision** (they mutate real reporting state from a
UI that will be recorded and demonstrated), **not** a correctness cleanup. That is a legitimate reason to
remove them — just not the stated one. Proceed with removal, and record the accurate reason.

#### 2.3.2 Remove the trigger controls

**Current behavior.** `components/reporting/BusinessReportingView.tsx:211–223` defines
`trigger(forceRefresh)` with `confirm()` prompts; L261–266 render the **Run now** and **Force refresh**
buttons; L255 renders **Load week**.

**Implementation.**
- Delete both buttons, the `trigger()` function, the `submitting` state that only serves them, the
  confirmation copy, and the now-unused `Play` / `RefreshCw` icon imports (L3).
- Keep **Load week** and the week selector exactly as they are.
- Keep the read-only pipeline status panel (last successful refresh, next scheduled refresh, staleness)
  — it is informational and is the honest replacement for manual triggering.
- Remove `["POST pipeline-runs", "/reporting/pipeline-runs"]` from `ALLOWED_ROUTES` in
  `app/api/reporting/[[...path]]/route.ts:12`, and drop the now-unused `POST` export if nothing else uses it.
- **Do not** remove the Central API endpoint or the worker's queue path — scheduled dispatch and
  operational/CLI triggering continue to rely on them.

#### 2.3.3 Add visualizations

**Available data.** `WeeklyPerformanceEntry` (`lib/reporting/types.ts`) per warehouse × client:
`inbound_units_count`, `outbound_orders_count`, `stockout_events_count`, `discrepancy_events_count`,
`discrepancy_rate`. `warehouse` is one of `los_angeles | zaragoza`. The endpoint returns **one week per
call** and accepts an optional `week_start` query parameter (`domains/reporting/router.py:25`).

**Charting approach — no new dependency.** Hand-rolled inline SVG components under
`uis/backoffice/components/reporting/charts/`. The backoffice has no charting library and a deliberately
minimal dependency set; adding one is a compliance-licensing decision the owner has not made.

**Validated palette.** These were checked with the data-visualization validator against the actual
backoffice surfaces — do not substitute untested colors.

- **Light** (surface `#fcfcfb`): `#3d7ab8`, `#ed7e4d`, `#3fae9f`, `#9a6ec4` — all checks pass.
- **Dark** (surface `#141d2b`, i.e. `ink-800`): `#5090cf`, `#dd7038`, `#22a08c`, `#a87fd4` — all checks pass.

Assign hues **in fixed order by entity** (Los Angeles = slot 1, Zaragoza = slot 2) so a filter never
repaints a series. The raw brand tokens (`navy #2b4d74`, `teal #6ebab8`, `sky #4b7aa6`) **fail** the
chroma/lightness checks as data colors and must not be used for marks — keep them for chrome, text, and
borders. Both palettes carry a sub-3:1 contrast warning on the warm/teal slots, which obligates visible
labels and a table view; the existing data table satisfies that and **must be kept**.

**Charts to build.**

1. **KPI stat tiles** (top row) — totals for inbound units, outbound orders, stockout events, and
   discrepancy events for the selected week, plus the existing status/staleness indicators. A number is
   the right form here; do not chart a single value.
2. **Grouped bar — outbound orders by client**, grouped by warehouse (2 series). Top N clients by volume
   with the remainder folded into "Other" — never generate additional hues.
3. **Grouped bar — inbound units by client**, same structure and same color assignment.
4. **Discrepancy rate by client** — horizontal bars sorted descending, with the value direct-labeled.
   Rate is a ratio: label as a percentage and keep a single axis.
5. **Trend line — week over week.** The only chart needing more than the current single-week payload.
   Fetch the **last 6 weeks** client-side by issuing parallel requests to the existing
   `weekly-warehouse-client-performance` endpoint with successive `week_start` values. **No backend
   change and no new BFF route.** Plot totals (not per-client) as one line per warehouse. Handle missing
   weeks as gaps, not zeros. If the added request volume is judged unacceptable at review, drop this
   chart rather than adding an endpoint — a new aggregate endpoint is out of scope for this spec.

**Chart construction rules (non-negotiable).**
- **Never a dual-axis chart.** Two measures with different scales get two charts.
- Legend present whenever ≥ 2 series; a single-series chart needs no legend box (the title names it).
  With ≤ 4 series also direct-label them, so identity is never carried by color alone.
- Text (values, labels, legends) uses the existing ink/neutral text tokens — never the series color.
- Thin marks; 4px rounded data-ends anchored to the baseline; 2px lines; ≥ 8px markers; a 2px surface gap
  between adjacent/stacked fills.
- Recessive grid and axes; selective direct labels, never a value on every point.
- Hover layer by default: per-mark tooltip on bars, crosshair + tooltip on the line chart, with hit
  targets larger than the marks.
- Dark mode is a **selected** palette (the values above), not an automatic filter/invert. Follow the
  existing `dark:` class conventions in the file.
- Empty and single-row weeks must render an explicit empty state, not a broken axis.
- Charts are `aria-hidden` decoration **only if** the same data is reachable in the retained table;
  otherwise give each an accessible name and description.
- Keep the existing table — it is both the accessibility relief for the contrast warning and the
  precise-value view.

**Acceptance criteria.**
- Run now and Force refresh are gone from the UI; the BFF no longer allowlists the POST; Load week and
  the read-only status panel still work.
- The reporting page leads with KPI tiles and charts, with the table retained below.
- Colors match the validated palettes exactly, in both light and dark mode.
- No chart uses two y-axes; every multi-series chart has a legend; series colors are stable when the
  client filter/top-N changes.
- Charts render correctly for an empty week, a one-client week, and a full week.
- No new dependency appears in `uis/backoffice/package.json`.
- `npm --prefix uis/backoffice run type-check`, `lint`, `build`, and `test` all pass.

**Tests.**
- vitest: chart components render expected mark counts for a fixture week; empty-state rendering; series
  → color assignment is stable when a series is filtered out; percentage formatting for discrepancy rate.
- vitest: the reporting view no longer renders Run now / Force refresh; Load week still triggers a fetch.
- vitest: BFF rejects `POST pipeline-runs` with 404 after the allowlist change.
- Manual: view the page at mobile and desktop widths in both themes; confirm no horizontal page scroll.

---

### 2.4 Ask AI opens the chat panel

**Current behavior.** The header control in `components/AppShell.tsx:57–63` is a
`<Link href="/">` labeled "Ask AI" — it navigates to the home route and nothing else. It is also
`hidden … sm:inline-flex`, so it does not exist on small screens. The chat slide-over lives **inside**
`components/knowledge/AskKnowledgeBox.tsx`, driven by that component's local
`const [panelOpen, setPanelOpen] = useState(false)` (L51), and the panel markup is rendered at L333+.
`AskKnowledgeBox` is mounted only by `components/HomeDashboard.tsx:21`. Consequently the panel can only be
opened from the home page, and only by submitting a query (L194), resuming a session (L226), or starting
a new chat (L249).

**Expected behavior.** Clicking Ask AI immediately opens the right-side chat panel — from any Back Office
route, before any query is submitted — behaving exactly as it does today once a query has been sent.

**Implementation — lift the panel to the protected layout.**

1. **New context** `uis/backoffice/lib/chat/panel-context.tsx`: `ChatPanelProvider` plus a `useChatPanel()`
   hook exposing `{ open, openPanel, closePanel }`. `openPanel()` accepts an optional seed question so the
   home box can keep its submit-then-open behavior.
2. **Extract the panel** into `uis/backoffice/components/knowledge/ChatPanel.tsx`. Move the slide-over
   markup and the session/message/WebSocket state (`sessions`, `activeSession`, `messages`,
   `connectionState`, the `lib/realtime/chat.ts` client wiring, `openSession`, `startNewChat`, `submit`,
   Escape handling, and the input focus effect) out of `AskKnowledgeBox`. Behavior must be preserved
   verbatim — this is a relocation, not a rewrite of the Engagement 10 chat client.
3. **Mount once** in `app/(protected)/layout.tsx`: wrap the existing tree in `<ChatPanelProvider>` and
   render `<ChatPanel />` inside it, alongside `<AppShell>`, so the panel is available on every protected
   route.
4. **`AskKnowledgeBox`** keeps only the home hero box (textarea, route `<select>`, suggestion buttons,
   history hint) and calls `openPanel({ question })` on submit. Keep the Engagement 10 fix that clears the
   textarea after submit.
5. **Header control** in `AppShell.tsx`: replace the `<Link href="/">` with a `<button type="button">`
   that calls `openPanel()`. Keep the `Sparkles` icon and current styling. Remove `hidden sm:inline-flex`
   so it is reachable on mobile, where the panel is already responsive.
6. **Opening must not create server state.** `openPanel()` with no question must **not** `POST /chat/sessions`.
   A session is created only when the first message is sent (today's behavior). Opening with an existing
   recent session should show that conversation; opening with none shows the empty composer.
7. **Accessibility.** The panel already uses `role="dialog"` + `aria-labelledby` and Escape-to-close.
   Add a focus trap while open and return focus to the invoking control on close. Keep `aria-expanded`
   on the header button.

**Acceptance criteria.**
- Clicking Ask AI from `/`, `/incidents`, `/suppliers`, `/backoffice/reporting`, `/agent-os`, and
  `/agent-os/rfp` opens the panel immediately without navigating away.
- The opened panel is identical to the post-query panel: history sidebar, agent-route select, composer,
  connection state.
- Opening the panel issues **no** network write; no empty chat session rows accumulate.
- The home Ask box still works: submitting opens the panel with that question in flight.
- Escape closes the panel and focus returns to the Ask AI button.
- Chat streaming, multi-turn ids, route selection, and reconnect snapshots behave exactly as before.

**Tests.**
- Update `uis/backoffice/tests/knowledge-ui.test.tsx` — it renders `<AskKnowledgeBox />` directly in seven
  places and will need the provider (and, for panel assertions, `<ChatPanel />`).
- New tests: header button opens the panel; opening fires no `POST /chat/sessions`; Escape closes and
  restores focus; the panel is reachable from a non-home route.
- Keep `uis/backoffice/tests/chat-realtime.test.ts` green — the transport must be untouched.

---

### 2.5 Remove the Business / Technical & Agent OS toggle

**Current behavior.** `components/ViewToggle.tsx` is rendered **twice** in `components/AppShell.tsx` —
L52 (desktop, `hidden md:block`) and L67 (a mobile strip below the header, `md:hidden`). It is backed by
`lib/backoffice/view-context.tsx`, whose provider wraps the tree in `app/(protected)/layout.tsx:5`.

**Dependency — this is the part that will break (decision D3).** `components/HomeDashboard.tsx` consumes
the same context:

```
const { view } = useBackofficeView();          // L13
{view === "business" ? <OperationsOverview /> : <TechnicalOverview />}   // L23
```

Deleting the toggle without a decision **orphans `components/TechnicalOverview.tsx`** — real content
(including the Qdrant/RAG cards that describe the knowledge base powering Ask AI) becomes unreachable.

**Expected behavior.** No top-center toggle. The left sidebar is the sole navigation. No content is lost.

**Implementation (recommended option).**
1. Give `TechnicalOverview` its own route: `app/(protected)/backoffice/technical/page.tsx` rendering the
   existing component unchanged.
2. Add a sidebar entry for it in `lib/backoffice/navigation.ts` under the existing **Technical Data**
   category, matching the established item shape (label, href, `lucide-react` icon).
3. `HomeDashboard` always renders `<OperationsOverview />`; drop the `useBackofficeView` import and the
   ternary. The live Operations Overview stays the landing view, consistent with the Engagement 6
   decision that made it the landing page.
4. Delete `components/ViewToggle.tsx` and both usages in `AppShell.tsx` (L52 and the L66–68 mobile strip,
   including its wrapper `<div className="border-t …">`).
5. Delete `lib/backoffice/view-context.tsx` and remove `BackofficeViewProvider` from
   `app/(protected)/layout.tsx` (import at L5, wrapper in the returned tree).
6. Update `uis/backoffice/tests/backoffice-layout.test.tsx`, which imports `BackofficeViewProvider` (L7).
7. Grep for any remaining `useBackofficeView` / `BackofficeView` references and remove them.

This partially advances the standing backlog item in
`docs/planning/remaining_planning/important_considerations/others.md` §3 ("rethink the current layout of
backoffice UI, now that agents are coming into the mix"). Note the progress there; do not attempt the
full IA restructure in this pass.

**Acceptance criteria.**
- No toggle appears in the header at any viewport.
- The Technical overview content remains reachable from the sidebar.
- The home page always shows the live Operations Overview.
- No dead exports, unused imports, or orphaned context files remain; `lint` and `type-check` pass.

**Tests.** Update the layout test; add a test asserting the header renders no toggle and that the new
technical route renders `TechnicalOverview`.

---

## 3. Dependencies and sequencing

- **Phase 1 and Phase 2 are independent** and may proceed in either order or in parallel. Phase 1 touches
  only `uis/website/`.
- **Within Phase 1:** 1.1 and 1.2 both edit the hero area/header of the same pages; do 1.1 then 1.2 to
  avoid conflicts.
- **Within Phase 2:**
  - **2.4 must land before or with 2.5.** Both edit `AppShell.tsx` and
    `app/(protected)/layout.tsx`; 2.4 adds a provider there and 2.5 removes one.
  - **2.1 is backend-first.** Fix data production before touching `AgentOSDashboard.tsx`; the dashboard
    is not the bug.
  - **2.2 and 2.3 are independent** of everything else.
  - 2.1 step 5 (DeepSeek pricing) is conditional on external verification and must not block the rest.
- **Blocked on owner sign-off:** D1 (§2.1 step 6), D2 (§2.3.1), D3 (§2.5).

---

## 4. Verification

Run for every touched package, per `AGENTS.md`:

```bash
npm --prefix uis/website run type-check && npm --prefix uis/website run lint && npm --prefix uis/website run test && npm --prefix uis/website run build
```

```bash
npm --prefix uis/backoffice run type-check && npm --prefix uis/backoffice run lint && npm --prefix uis/backoffice run test && npm --prefix uis/backoffice run build
```

For Central API changes, run the pytest suite from `services/central-api/` with its `.env` moved aside for
CI parity, then restore it and re-seed if the run truncated local data.

Meet the release gates in `docs/standards/production-readiness.md`: tests pass, coverage preserved,
failure paths handled, no sensitive data logged.

### Local end-to-end verification

The Engagement 10 realtime features (SSE + WebSocket chat) use a same-origin `/realtime` path that
production serves via a Traefik rule. `next dev` cannot proxy WebSocket upgrades, so browse through a
local reverse proxy that routes `/realtime/*` to Central API and everything else to Next, and add that
proxy origin to `CENTRAL_API_CORS_ORIGINS`. Sign in as a user **with a jurisdiction** —
`rfp-demo@trackflow.local`. The login page's "Admin Demo" autofill account has `jurisdiction: null`,
which makes every agent/chat write fail with a 403 that the BFF masks as a generic "Not authorized".

> **Worth fixing before the recording:** either assign the demo admin account a jurisdiction, or repoint
> the login-page autofill at an account that has one. Otherwise the advertised demo credentials cannot use
> the headline AI features. Consider also surfacing the real reason instead of the masked
> "Not authorized" — it is confusing even to a developer.

---

## 5. Documentation to update

Per the `AGENTS.md` pre-commit workflow, update the docs that move together:

| Doc | Update |
|---|---|
| `README.md` | "What's Been Built" if the reporting/RFP/Agent OS surfaces change materially |
| `CLAUDE.md` | "Where New Engagement Code Goes" — note the RFP download route, the Agent OS telemetry fixes, and the Back Office nav change |
| `memory-bank/progress.md` | Record this polish pass and its outcomes |
| `docs/runbooks/business-performance-pipeline.md` | Note that the Back Office no longer exposes manual trigger controls and that triggering is now scheduled/CLI-only — and that this is a UI decision, not a Prefect consequence |
| `docs/runbooks/telemetry-inventory.md` | Add the newly populated agent telemetry signals (RFP tokens/cost, output previews) and the `AGENTS_STORE_CONTENT` posture |
| `docs/briefs/09-agentic-workflows.md` | Status note for the final-document download — **protected path**: status-only edits, with confirmation |
| `uis/website/README.md`, `uis/backoffice/README.md` | Folder READMEs for the changed surfaces |
| `docs/planning/remaining_planning/important_considerations/others.md` | Note partial progress on the Back Office IA item |

Do not modify `docs/briefs/` beyond status corrections, `docs/archive/`, `docs/standards/visibility.md`,
or `packages/shared/` — these are protected paths.
