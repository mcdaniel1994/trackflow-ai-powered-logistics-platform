# Specification — Engagement 10: Real-Time Systems

**Status:** owner-approved; Phases 0–2 merged through PR #35; Phases 3–5 implemented, awaiting review
**Author:** drafted 2026-08-18 from the planning inputs in [`10_realtime/`](10_realtime/)
**Supersedes:** nothing. The three planning inputs
(`realtime_instructions.md`, `real_systems_part1.md`, `real_systems_part2.md`) remain the
requirement source; §9 records every deliberate departure from them.
**Stakeholder brief:** [`docs/briefs/10-realtime-systems.md`](../../briefs/10-realtime-systems.md)

---

## 0. What this engagement delivers

Two graded deliverables, shipped as two pull requests against `main`, planned here as one design
because they share a transport, an authentication decision, and a pub/sub layer.

| Part | Branch | Deliverable |
|---|---|---|
| **Part 1** | `feature/sse-notifications` | Server-Sent Events push of `rfp_ticket_created` to the RFP Desk, replacing manual refresh |
| **Part 2** | `feature/websocket-chat` | WebSocket token streaming for the first-line CX agent, with mid-response interrupt and reconnect-rehydrate |

A third workstream — persistent, per-user chat history and the chat UI rework — is owner-requested
scope that is not in the planning inputs. It is required for Part 2's rehydrate criterion and is
specified in §5.

### 0.1 Decisions locked by the owner (2026-08-18)

| # | Decision | Rationale |
|---|---|---|
| 1 | **Cookie auth is retained.** No browser-side bearer token. | The assignment's `Authorization: Bearer` requirement assumes a token-in-JS frontend, which this repo deliberately does not have. See §9.1. |
| 2 | **Same-origin path routing at Traefik** (`/realtime/*` → `central-api`). | Preserves the host-only cookie, adds no CORS surface, and lets Traefik handle the WebSocket upgrade natively. See §2. |
| 3 | **Streams bypass the Next.js proxy entirely.** | Consequence of decision 2; the 15 s `AbortSignal.timeout` in `lib/server/proxy.ts` is left unchanged. |
| 4 | **SSE events are owner-scoped**, matching existing ticket authorization. | No authorization change, no cross-tenant leak. See §4.4. |
| 5 | **Chat history persists for 90 days**, per user, under an explicit standards exception. | See §5.2 and §8.2. |
| 6 | **Auto-routing stays; a manual override picker is added.** | The Engagement 8 graph already orchestrates. A second dispatch tier would duplicate it. See §5.4. |
| 7 | **The RFP Desk stays its own page** and is not a picker target. | Upload and approval exist only on that page; a picker entry that cannot perform them is a dead end. Revisit later if desired. |

---

## 1. Findings that shape the design

These were established by reading the code, not assumed. They are the reason several requirements
are met differently than the planning inputs describe.

1. **There is no browser-side JWT.** Authentication is an httpOnly cookie plus double-submit CSRF
   ([`core/dependencies.py`](../../../services/central-api/central_api/core/dependencies.py)). The
   browser calls Next.js route handlers, which proxy to Central API forwarding cookies
   ([`lib/server/proxy.ts`](../../../uis/backoffice/lib/server/proxy.ts)).
2. **Central API is not publicly reachable.** In `compose.coolify.yaml` it is `expose: ["8000"]`
   only. The single public entrypoint is `backoffice.forgehub.cloud` → the Next.js backoffice.
   Coolify assigns that domain in its UI; there are no Traefik labels in the compose file today.
3. **Next.js App Router route handlers cannot proxy a WebSocket upgrade.** Part 2 therefore cannot
   route through the existing proxy under any configuration.
4. **Central API runs one uvicorn worker, one replica**
   ([`docker/central-api.Dockerfile:20`](../../../docker/central-api.Dockerfile)). An in-process
   pub/sub is correct here rather than a compromise — and a blocking handler stalls the whole
   service, which is why §3.3 exists.
5. **Every existing endpoint is synchronous.** Zero `async def` across all domain routers;
   `run_agent` calls `graph.invoke()` (blocking).
6. **The first-line CX agent already exists.** The Engagement 8 routing prompt opens with "You route
   a TrackFlow customer-experience question"
   ([`domains/agents/routing.py:24`](../../../services/central-api/central_api/domains/agents/routing.py))
   and routes across policy/returns/SLA knowledge and live ticket lookup — exactly the Part 2
   CONTEXT's description. **No new agent is built.** It is labelled `first_line_cx`.
7. **No chat messages are stored, by design.** `AgentConversation` records an owner boundary only;
   `docs/standards/telemetry-standard.md:122` keeps prompts and completions out of storage. Part 2's
   rehydrate criterion cannot be met without an explicit exception (§8.2).
8. **Multi-turn is not wired in the UI.** `askAgent()` in
   [`lib/agents/api.ts`](../../../uis/backoffice/lib/agents/api.ts) never sends `conversation_id`,
   even though the API accepts it.
9. **RFP tickets have one creation path.**
   [`create_from_upload`](../../../services/central-api/central_api/domains/rfp/service.py) sets
   `status="analyzing"` then schedules intake via `BackgroundTasks` — a single, unambiguous emit point.
10. **`AskKnowledgeBox` does not clear its textarea after submit** — the text remains and must be
    manually deleted before the next query. A defect, fixed in §5.3.

---

## 2. Transport and routing

### 2.1 Traefik path routing

Central API gains a `/realtime` mount. A Traefik router on the existing host
`backoffice.forgehub.cloud` matches `PathPrefix(/realtime)` at a priority above the backoffice
catch-all and forwards to `central-api:8000`. All other Central API paths remain internal.

Consequences, all of them the point of choosing this over a subdomain:

- The auth cookie stays **host-only** — no widening to `Domain=.forgehub.cloud`.
- **No CORS** configuration changes; requests are same-origin.
- Traefik performs the **WebSocket upgrade** natively.
- SSE never traverses the Next proxy, so its request timeout is untouched.

### 2.2 Phase 0 verification (blocking)

Coolify must permit custom Traefik labels alongside its generated ones. This is verified against the
running VPS **before any transport code is written**. If it cannot be done, the documented fallback
is a second Coolify domain for Central API restricted to `/realtime`, which then requires the cookie
`Domain` widening and a CORS entry — a materially worse posture that the owner must approve
separately.

### 2.3 Authentication on streams

Both the SSE endpoint and the WebSocket authenticate with the **same cookie-borne JWT as every other
backoffice route**, through the existing `trackflow_auth` verifier.

- **SSE:** `current_principal` on connect. Unauthenticated connections are refused before any frame.
- **WebSocket:** the principal is verified during the handshake, before the socket is accepted and
  before any chat event is processed. Because the connection is same-origin, the cookie is present
  on the upgrade request; no `?token=` query parameter is used, which also keeps credentials out of
  proxy and access logs.
- The client consumes SSE with `fetch` + `ReadableStream` as the assignment requires — not
  `EventSource`, which cannot carry the CSRF header either.

---

## 3. Shared runtime

### 3.1 In-process pub/sub

One event bus module, two topic families:

| Topic | Producer | Consumers |
|---|---|---|
| `rfp.tickets.<owner_user_uuid>` | RFP ticket creation | that owner's SSE streams |
| `chat.<session_id>` | the agent generation task | that session's WebSocket connections |

Publishers never hold a reference to a connection; subscribers receive from a bounded per-connection
queue. A slow or dead consumer drops its own oldest events and is disconnected past a threshold — it
can never apply backpressure to the producer or to another subscriber. This satisfies the Part 2
producer/consumer requirement, and single-worker deployment makes it correct without Redis (the Part
2 CONTEXT explicitly permits in-memory for a single process).

### 3.2 Multi-connection fan-out

Several connections may subscribe to the same topic — two dashboards for one user, or a supervisor
watching a chat session. The agent is invoked **once** per generation; its tokens are published once
and fanned out to every subscriber. This is the substantive answer to both parts' design questions
about concurrent viewers.

### 3.3 Async boundary

Scoped narrowly and deliberately:

- New `/realtime` handlers are `async`.
- The agent gains an `astream` path for token production.
- **Streaming handlers never hold a sync DB session for the life of the stream.** Database work
  happens in short, explicit units; with one worker, a held connection or a blocking call inside a
  long-lived handler stalls the entire service.
- The ~40 existing synchronous endpoints are **not** converted. Broad conversion is risk without
  payoff.

---

## 4. Part 1 — SSE and the RFP notification

### 4.1 Endpoint

`GET /realtime/rfp/stream` — `Content-Type: text/event-stream`, `Cache-Control: no-cache`,
`X-Accel-Buffering: no`, with periodic keep-alive comment frames so intermediaries do not close an
idle connection.

### 4.2 Event

Named event `rfp_ticket_created`, emitted the moment a ticket is created with `status = analyzing`.
The `data:` line is a flat JSON object of ticket fields — not a nested `{"event","data"}` envelope —
using the field names already in `rfp_tickets`:

```text
event: rfp_ticket_created
id: <monotonic event id>
data: {"ticket_id":"…","rfp_id":"…","client_name":"…","client_country":"US","services_requested":["warehouse"],"status":"analyzing","created_at":"2026-08-18T14:32:00Z"}
```

No document text and no per-department sections — only what a watcher needs to decide whether it
needs attention now.

### 4.3 Emit point

Publication occurs in the RFP service after the ticket row is committed, so no event can announce a
ticket that a subsequent read would not find.

### 4.4 Authorization scope

Events are delivered **only to the connected principal's own tickets**, matching
`list_tickets(principal.user_id)`. Team-wide fan-out would require a commercial-role read scope and
an authorization change; that is out of scope and noted as a future option.

### 4.5 Client

- Consumes via `fetch` + `ReadableStream` with an incremental SSE frame parser.
- **Reconnect with progressive backoff** and jitter, capped, with an explicit "reconnecting"
  indication — the stream never silently stops notifying.
- **Recovery strategy (chosen and documented): refetch-then-stream.** On every connect and
  reconnect, the client refetches the ticket list and only then applies subsequent SSE events. The
  list is authoritative; the stream carries deltas after it. Chosen over `Last-Event-ID` replay
  because it needs no server-side event buffer, cannot miss an event that arrived during the gap,
  and reuses an endpoint that already exists.
- **Deduplication by `ticket_id`**, so a ticket present in the refetch and also delivered by the
  stream appears once.
- The new-ticket notification is **visually distinct** from ordinary dashboard rows, and arrival
  updates only the affected item — no full reload, no refetch-everything per event.
- `useAutoRefresh` polling is removed from the RFP Desk view.

### 4.6 No model calls

Part 1 contains no call to any model or agent. This is an explicit grading criterion and is asserted
in review.

---

## 5. Chat persistence and UI rework

Owner-requested scope, and a prerequisite for Part 2's rehydrate criterion.

### 5.1 Schema

New migration (next revision after `20260805_0017`), two tables:

- **`chat_sessions`** — `session_id`, `agent_id` (`first_line_cx`), `user_id`, `client_id`,
  `status` (`active` | `interrupted` | `closed`), `created_at`, `updated_at`. Field names follow the
  Part 2 CONTEXT exactly. `session_id` doubles as the LangGraph `thread_id`.
- **`chat_messages`** — `message_id`, `session_id`, role, content, `sequence`, `interrupted` flag,
  `created_at`. Owner-scoped through its session; indexed for ordered reads.

RFP notification payloads are never mixed into the chat contract, per the Part 2 CONTEXT constraint.

### 5.2 Retention

**90 days**, enforced by the existing maintenance worker alongside current retention jobs, and
recorded in `docs/runbooks/telemetry-inventory.md`. Deletion is documented, not implicit.

### 5.3 Chat surface

- **Slide-over panel:** opens the instant a query is sent — right-side drawer on desktop,
  full-screen sheet on mobile. Focus management and dismissal follow existing accessibility practice
  in the repo.
- **Textarea clears on send** (fixes the §1.10 defect).
- **Session history:** a list of the user's previous sessions; selecting one restores its
  conversation. `conversation_id` / `session_id` is threaded through `askAgent()`, which today drops
  it (§1.8), so multi-turn works in the UI for the first time.
- Existing dark mode, theming, and shell conventions are respected.

### 5.4 Agent picker

A selector on the chat input defaulting to **Auto** — today's behavior, where the Engagement 8 graph
classifies and routes. Explicit options (**Knowledge base**, **Ticket lookup**) pin the route and
skip the classifier, which is faster, cheaper, and an escape hatch when Auto misroutes. The response
surfaces which route was taken, so Auto is legible rather than opaque.

No orchestration tier is added above the existing routing node. Two components deciding the same
question is a defect, not a feature.

---

## 6. Part 2 — WebSocket chat streaming

### 6.1 Endpoint

`GET /realtime/chat/{session_id}` (upgrade). The handshake verifies the cookie principal, confirms
the session exists and belongs to that principal, and only then accepts the socket. Unauthenticated
or unauthorized upgrades are rejected before any chat event.

### 6.2 Event contract

Named events with structured payloads, per the Part 2 CONTEXT:

| Event | Direction | Purpose |
|---|---|---|
| `user_message` | client → server | a new user turn |
| `token_chunk` | server → client | one token, with `session_id` and `sequence` |
| `interrupt_requested` | client → server | abort current generation, optionally carrying `new_input` |
| `generation_interrupted` | server → client | partial message marked `interrupted` |
| `generation_completed` | server → client | terminal message id for the turn |
| `session_snapshot` | server → client | full history on connect/reconnect |

### 6.3 Streaming and interrupt

- Answer deltas stream from the existing agent's provider call inside the LangGraph generation node,
  are checked by the output guardrail before publication to `chat.<session_id>`, and are then fanned
  out (§3.2). This preserves the real provider stream while keeping the existing graph, agent, and
  tools intact; see §9.7 for why this repository does not use `stream_mode="messages"`.
- **Interrupt genuinely aborts generation** — the running task is cancelled and the model stream
  stopped, so no further `token_chunk` is produced for that generation. It is *not* implemented by
  ignoring a response that still arrives.
- **LangGraph HITL `interrupt()` is not used** for this. Stream abort and graph pause are different
  mechanisms; conflating them is called out explicitly in the assignment and in the PR answers.
- After abort: the partial assistant message is **persisted and marked interrupted**, never deleted
  or overwritten. The redirected reply begins a **new turn** reflecting `new_input`.

### 6.4 Reconnect and rehydrate

Progressive backoff, same discipline as Part 1. On reconnect the client sends the same `session_id`
and receives `session_snapshot` — the conversation restored from `chat_messages` (and checkpoint
where applicable) — **before** any new token is accepted. Restoring context, not merely reopening a
socket.

---

## 7. Testing

Per `.agents/rules/testing-error-handling-ci.md`. Tests live under `services/central-api/tests/` and
`uis/backoffice/tests/`, following repo convention rather than the assignment's bare `tests/` (§9.3).

**Part 1**
- SSE response headers include `text/event-stream`.
- The wire carries a named `event: rfp_ticket_created` line and a `data:` JSON body matching the
  §4.2 field shape — asserted against real framing, not an abstract dict.
- Unauthenticated connections are refused.
- Events are owner-scoped: another principal's ticket is never delivered.
- Reconnect/recovery: backoff fires, the refetch recovers tickets created during the gap, and no
  `ticket_id` is rendered twice.
- No model or agent call occurs on the Part 1 path.

**Part 2**
- Event contract: `token_chunk`, `generation_interrupted`, `generation_completed`.
- Interrupt mid-response stops further tokens from the original generation, leaves the partial
  message marked interrupted, and the next reply is a new turn reflecting `new_input`.
- Reconnect with the same `session_id` restores the thread, not an empty chat.
- Unauthenticated or cross-owner handshakes are rejected.

**Persistence**
- Retention prunes at 90 days; session and message reads are owner-scoped.

Where a browser-level behavior cannot be asserted in CI, documented manual verification is recorded
in the PR, as the assignment permits.

---

## 8. Standards, security, and compliance

### 8.1 Applicable rules

`.agents/rules/authentication-security.md` (stream auth, session ownership),
`.agents/rules/database-engineering.md` (new tables, migration, retention),
`.agents/rules/telemetry.md` (§8.2 below),
`.agents/rules/testing-error-handling-ci.md`,
`.agents/rules/public-ui-visibility.md` (chat surface),
`.agents/rules/compliance-licensing.md` (if any dependency is added).

### 8.2 Telemetry standard exception — required

`docs/standards/telemetry-standard.md:122` keeps raw prompts and completions out of storage, and the
agents domain stores no message text by design. **Storing chat history is a deliberate, documented
exception**, scoped to the `chat_messages` table only:

- It does **not** relax the agent trace store, which continues to hold safe metadata only.
- Retention is bounded at 90 days with enforced deletion.
- Rationale (user-facing chat history is a product requirement, unlike trace telemetry) is recorded
  in the standard and the runbook.

### 8.3 Personal data

Chat messages are the platform's first stored user-generated free text. The Part 2 CONTEXT describes
B2C parcel recipients as eventual users, which is the same category of real personal data that
[`important_considerations/others.md`](important_considerations/others.md) flags as retiring the
disposable-data waiver. In the deployed portfolio environment the only author is the owner, so
present risk is negligible — but the exception is taken **deliberately and in writing** rather than
drifted into, and any future external-facing chat requires a backup and retention decision first.

### 8.4 Feature flags

Realtime is flag-gated and **off by default**, consistent with `AGENTS_ENABLED` and `RFP_ENABLED`
(both currently `false` in production). Enabling the demo requires `RFP_ENABLED` for Part 1 and
`AGENTS_ENABLED` for Part 2.

---

## 9. Deliberate departures from the planning inputs

Each is a graded requirement met differently, surfaced per the precedence rule in
[`README.md`](README.md) §1.3 rather than silently resolved.

1. **`Authorization: Bearer` → cookie.** The assignment mandates a bearer header because it assumes a
   token-in-JS frontend. This repo deliberately has none; introducing one to satisfy a checkbox would
   weaken a real security boundary. The *substance* — the stream requires the same JWT as the
   backoffice API, unauthenticated clients receive nothing, and the client uses `fetch` +
   `ReadableStream` rather than `EventSource` — is met exactly.
2. **WebSocket `?token=` → cookie on a same-origin upgrade.** The assignment suggests a query-string
   token because browsers cannot set `Authorization` on a WebSocket handshake. Same-origin routing
   makes the cookie available on the upgrade instead, which is strictly better: no credential in
   URLs, proxy logs, or history.
3. **Test location.** `services/central-api/tests/` and `uis/backoffice/tests/` rather than a
   top-level `tests/`, following repo convention. No delivery folder is created, as instructed.
4. **No new CX agent.** The existing Engagement 8 agent *is* the first-line CX agent (§1.6); it is
   labelled, not rebuilt — consistent with the assignment's "don't change its logic or tools".
5. **Owner-scoped notifications** rather than team-wide (§4.4).
6. **Additional scope:** persistent chat history, the slide-over panel, the textarea fix, and the
   agent picker are owner-requested and not in the planning inputs.
7. **LangGraph `stream_mode="messages"` → provider callback inside the existing generation node.**
   The existing first-line agent calls the OpenAI-compatible DeepSeek SDK from its LangGraph
   generation node and returns a structured JSON object containing both `answer` and an optional
   memory candidate. LangGraph message mode cannot expose that nested provider stream without
   replacing the established generation boundary or duplicating agent logic. The implementation
   therefore opts the same provider call into streaming, incrementally decodes only the `answer`
   field, applies the existing output guardrail before each browser-visible delta, closes the
   provider stream on interruption, and rebuilds the same structured result for the graph. This
   satisfies the underlying real-token-streaming and genuine-abort requirements without streaming
   memory metadata or adding a second agent.

---

## 10. Phasing

An owner review-and-approval pause follows every phase, per the working agreement.

| Phase | Scope | Branch |
|---|---|---|
| **0** | Traefik label verification on the VPS (§2.2); standards exception written; brief created | — |
| **1** | `/realtime` mount, stream auth, in-process pub/sub, async boundary | `feature/sse-notifications` |
| **2** | SSE endpoint, `rfp_ticket_created` emit, RFP Desk client, tests → **PR 1** | `feature/sse-notifications` |
| **3** | `chat_sessions` / `chat_messages`, migration, retention, standards exception landed | `feature/websocket-chat` |
| **4** | Chat UI rework: slide-over, session history, textarea fix, agent picker | `feature/websocket-chat` |
| **5** | WebSocket endpoint, token streaming, interrupt/abort, rehydrate, tests → **PR 2** | `feature/websocket-chat` |
| **6** | Deployment, flag enablement, runbook updates, design-question answers in both PRs | — |

Phase 0 is blocking: if §2.2 fails, phases 1–5 change shape and the fallback needs separate approval.

---

## 11. Owner approvals

1. ✅ This specification is binding.
2. ✅ The telemetry standard exception in §8.2 is approved.
3. ✅ Repository preparation for same-origin `/realtime` exposure is approved; actual deployment and
   feature enablement remain separately gated.
4. ✅ Phase 0 confirmed Coolify retains the custom labels, so the fallback was not required.
