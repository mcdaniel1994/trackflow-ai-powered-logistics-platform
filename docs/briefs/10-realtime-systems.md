# Brief: Real-Time Systems — Push Notifications and Streaming Chat

## Client: TrackFlow · Stakeholders: Miguel Torres (Commercial Director) · Valentina Cruz (Customer Experience)

## Status

Complete — Engagement 10 implementation is merged to `main`. The owner approved the binding specification:
[`docs/planning/remaining_planning/spec-10-realtime.md`](../planning/remaining_planning/spec-10-realtime.md).
Phase 0 is verified and Part 1 (Phases 1–2) merged to `main` through PR #35 on 2026-08-18. Phases
3–5 chat persistence, bounded 90-day retention, owner-scoped HTTP session history, the responsive
chat slide-over, route picker, WebSocket token streaming, genuine interrupt, and reconnect
rehydration merged through PR #36 on 2026-08-18, and the owner accepted the implementation as
complete. The two graded deliverables shipped as `feature/sse-notifications` (Part 1) and
`feature/websocket-chat` (Part 2). Phase 6 production rollout is explicitly deferred: no production
mutation occurred, and `RFP_ENABLED` / `AGENTS_ENABLED` remain off by default.

## Background

The platform is complete enough that its remaining weakness is a communication one. Engagement 9's
RFP Desk registers every incoming proposal request as a ticket and moves it through intake, drafting,
evaluation, and departmental approval — but the only way anyone learns a ticket arrived is by opening
the dashboard and looking. Engagement 8's agent answers customer-experience questions well, but it
answers all at once, after a wait, through a single request/response call.

Both gaps are about *channel*, not capability. Nothing about the RFP workflow or the agent's
reasoning changes in this engagement. What changes is how the backend reaches the browser.

## Stakeholder Requests

> **Miguel Torres, Commercial Director:** "Every RFP that comes in is money on the table, and right
> now nobody finds out until they open the dashboard on their own. I need the screen to show it by
> itself the moment a new RFP ticket is registered, without anyone having to refresh. And if
> someone's connection drops, it should reconnect without them having to reload the page."

> **Valentina Cruz, Customer Experience:** a client sends a message, waits, and gets the whole answer
> in one shot. If the agent is answering the wrong intent — tracking when they meant a return — they
> cannot redirect it until the reply finishes. Stream the answer token by token, and let the client
> interrupt mid-response so the chat feels like a real conversation.

The tech lead's two tickets frame the work: (1) SSE push notification for new RFP tickets, (2)
WebSocket token streaming with interrupt for the first-line CX agent.

## Assignment

Source requirements are the three planning inputs in
[`docs/planning/remaining_planning/10_realtime/`](../planning/remaining_planning/10_realtime/):
`realtime_instructions.md` (both parts), `real_systems_part1.md` (RFP/SSE context), and
`real_systems_part2.md` (chat/WebSocket context). They are requirements and constraints, not
architecture; the specification records every deliberate departure and why.

## What You're Building

### Part 1 — SSE notification (`feature/sse-notifications`)

An SSE endpoint that emits a named `rfp_ticket_created` event the moment a ticket enters
`status = analyzing`, carrying the ticket identifier, its RFP id, client name and country, requested
services, status, and creation time — the existing `rfp_tickets` field names, not new ones. The RFP
Desk consumes it with `fetch` + `ReadableStream`, reconnects with progressive backoff, recovers
tickets registered while disconnected via refetch-then-stream, and deduplicates by `ticket_id`. The
notification is visually distinct from ordinary dashboard rows. Polling is removed from that view.

**No model or agent call exists anywhere on this path.** This is a communication layer.

### Part 2 — WebSocket chat streaming (`feature/websocket-chat`)

A WebSocket bound to an existing conversation by `session_id` (also the LangGraph `thread_id`),
streaming the first-line CX agent's response token by token. A mid-response interrupt genuinely
aborts the running generation rather than discarding a response that still arrives; the partial
message is kept and marked interrupted, and the redirected reply starts a new turn. Reconnect with
the same `session_id` rehydrates the conversation before accepting new tokens. Agent event production
is decoupled from socket consumers by a per-session pub/sub channel.

The agent itself is unchanged. The Engagement 8 agent already *is* the first-line CX agent — its
routing prompt classifies TrackFlow customer-experience questions across policy knowledge and live
ticket lookup — so it is labelled `first_line_cx`, not rebuilt.

### Owner-requested addition — chat persistence and UI rework

Not in the assignment, and required for Part 2's rehydrate criterion: per-user chat sessions and
message history persisted for 90 days, a session list users can return to, a slide-over chat panel
(right-side drawer on desktop, full-screen sheet on mobile) that opens the moment a query is sent, a
fix for the input that currently does not clear after submit, and an agent picker defaulting to Auto
with manual override.

## Key Decisions

| Decision | Summary |
|---|---|
| Authentication | The existing httpOnly cookie + CSRF, not a browser-side bearer token. The repo has no token-in-JS frontend and will not gain one. |
| Routing | Same-origin Traefik path routing (`/realtime/*` → Central API) on the existing public host. Preserves the host-only cookie, adds no CORS, handles the WebSocket upgrade natively. |
| Notification scope | Owner-scoped, matching existing ticket authorization. No cross-tenant delivery. |
| Pub/sub | In-process, one channel per topic. Correct because Central API runs a single worker; no Redis. |
| Async | New realtime handlers only. The ~40 existing synchronous endpoints are not converted. |
| Chat history | Persisted for 90 days under an explicit, documented exception to the telemetry standard. |

## Acceptance Criteria

- The RFP Desk shows a new ticket automatically, with no manual action.
- Dropping and restoring the connection triggers backoff reconnection, applies the documented
  recovery strategy, and duplicates nothing.
- Both streams require the same authentication as the backoffice API; unauthenticated clients receive
  no events.
- Events are named with structured payloads — never a single generic message type — and tests assert
  real SSE framing (`text/event-stream`, event name, JSON data shape).
- Chat tokens render as they are generated; interrupt measurably stops further tokens from the
  original generation, the partial message stays and is marked interrupted, and the next reply is a
  new turn reflecting the new input.
- Reconnect restores the conversation thread rather than an empty chat.
- Field and entity names match the Part 1 and Part 2 contexts, and the two contracts are never mixed.
- Design-question answers are included in each pull request description.

## Out of Scope

- Any change to RFP workflow logic, agent reasoning, agent tools, or agent memory.
- Team-wide or role-based notification fan-out (would require an authorization change).
- An external pub/sub backplane such as Redis.
- Adding the RFP Desk as a chat picker target — upload and approval exist only on its own page.
- Broad conversion of existing synchronous endpoints.
