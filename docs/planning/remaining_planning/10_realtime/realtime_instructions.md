
## Milestone — Real-Time Systems: SSE Notifications (Part 1 of 2)

**Before you start**: read your `CONTEXT-company.md` before writing any code — it defines the operational events, field names, and company-specific constraints for this part.

## 🎯 Your challenge

📌 You're building on *your copy* of the monorepo for the company you were assigned at the start of the course — not a new repository.

You already have a working central API, a reporting pipeline feeding business metrics, and the multi-agent RFP generation system with checkpointing your team shipped last week. That system registers every new proposal request (RFP) as a ticket that needs processing — but right now, the only way anyone finds out a new ticket arrived is by manually refreshing the dashboard. The sales team filed an *RFI*: they want to know why nobody notices a new RFP until someone checks the screen out of curiosity. Your tech lead turned that question into a *ticket* for your squad: replace that manual refresh with a flow that pushes the notification to the frontend the moment an RFP ticket is registered.

The brief is concrete. Your manager summarizes it like this:

> "Every RFP that comes in is money on the table, and right now nobody finds out until they open the dashboard on their own. I need the screen to show it by itself the moment a new RFP ticket is registered, without anyone having to refresh. And if someone's connection drops, it should reconnect without them having to reload the page."

Some requirements are left implicit in this brief, and you'll need to identify them carefully: the notification must be distinguishable from other event types already on your dashboard (it's not just another generic event), it must indicate at least which RFP ticket arrived and that it needs processing, and it must degrade gracefully if the client loses connection — not silently stop notifying.

*Out of scope for this part:* this deliverable requires no calls to a model or agent. This is a communication layer, not an AI layer — that comes in Part 2.

## 🌱 How to Start the Project

Keep working on the fork of your company's monorepo that you've been using since Milestone. If for some reason you don't have your fork yet, create it now from the base monorepo.

1. Create a new branch from your main branch: `feature/sse-notifications`.
2. Locate the service and dashboard view that currently depend on polling — you will extend those paths, not create a parallel app or a delivery folder.
3. Check your `CONTEXT-company.md` to confirm how an RFP ticket is represented (fields, initial status) — that defines what the real-time notification must carry.
4. Add any new dependencies with `uv add` (backend) / your UI package manager as already used in the monorepo — never with `pip install` or `pipenv`.
5. Implement under the existing layout: SSE in `services/`, consumer UI in `uis/`, tests in `tests/`.

If you need a refresher on how to set up a project, check out how to start a coding project.

## 💻 What You Need to Do

**Backend (`services/`)**
- [ ] Implement an SSE endpoint that emits an event every time a new RFP ticket is registered in the system
- [ ] Define an explicit event name (e.g. `rfp_ticket_created`) and a consistent payload with at least the ticket identifier and its initial status (avoid a generic "message"-type event)
- [ ] Correctly configure the SSE connection's headers and keep-alive so it doesn't close prematurely (`Content-Type: text/event-stream`, and keep-alive comment frames as needed)
- [ ] Protect the stream with the *same JWT* used by the backoffice API — unauthenticated clients must not receive events

⚠️ *IMPORTANT:* field names, entities, and domain values in your implementation must match what's specified in your `CONTEXT.md`. A generic implementation that ignores the context will not be accepted.

**Frontend (`uis/`)**
- [ ] Refactor the existing dashboard view that currently requires a manual reload so it shows a new RFP ticket arriving in real time, consuming the SSE stream
- [ ] Consume the stream using `fetch` + `ReadableStream` (or your stack's equivalent), sending the JWT (e.g. `Authorization: Bearer …`). Do *not* rely on `EventSource` alone — it cannot set custom auth headers cleanly, which is why `fetch` is required here
- [ ] Implement reconnection with progressive backoff when the connection drops
- [ ] Implement at least one *recovery strategy* so events registered while disconnected are not silently lost. Acceptable options (pick one and document it): `Last-Event-ID` / short server-side replay; refetch the ticket list on reconnect and use SSE only for events after that; or an equivalent approach. Deduplicate so the same ticket never appears twice in the UI
- [ ] The notification for a new RFP ticket is visually distinguishable from other dashboard data and doesn't require reloading the page or re-fetching all the data on every event

**Testing (`tests/`)**
- [ ] Test the SSE endpoint itself: assert response headers include `text/event-stream`, the wire uses a named event: (e.g. `rfp_ticket_created`), and `data:` is JSON matching the required payload shape / CONTEXT fields — not only an abstract dict unit test detached from the SSE framing
- [ ] Test, or documented manual verification, of reconnection + recovery after a dropped connection (backoff fires, missed tickets are recovered or explicitly handled, no duplicate UI for the same `ticket_id`)

## 🎁 Optional: Another Real-Time Notification Case

The RFP ticket is your required deliverable. If you want extra practice (this is not required to pass this part), you can implement *a second type of push notification*, reusing the same SSE endpoint with a new event name. Pick at most one of these, whichever best fits what you've already built and your CONTEXT:
- *Business metric threshold alert* — notify when a metric from your reporting pipeline crosses the critical threshold your CONTEXT defines for your company (for example, a sales drop, a no-show rate, or a billing denial rate, as applicable).
- *Agent escalation* — notify when a conversation is escalated from agent to human, so whoever is supervising sees it appear on the dashboard without reloading.
- *Operational inactivity alert* — notify when a process or location fails to register expected activity within a defined period (for example, no sales registered within a time window, or a vacancy left unfilled past the expected deadline).

If you implement one of these, it must meet the same technical bar as the RFP notification: named event, structured payload, and compatible with the reconnection logic you already built.

## 🤔 Design Questions

Before considering your implementation done, think through and document your answers to these questions in your PR:
- If two people on the sales team open the dashboard at the same time, should each SSE connection be independent, or should they share some intermediate layer? What would happen if 50 people opened it at once?
- Which recovery strategy did you choose for tickets registered while disconnected (`Last-Event-ID` / short replay, refetch-then-SSE, or equivalent), and how do you prevent duplicates after reconnect?
- Why is SSE the right tool for notifying that a ticket arrived, and not WebSockets? At what point would that stop being true — for example, if you wanted someone to be able to react to the ticket from the same channel?

## ✅ What We Will Evaluate
- [ ] The dashboard shows the new RFP ticket notification automatically, with no manual action from the user
- [ ] Dropping and restoring the network connection triggers reconnection within the backoff scheme, applies the documented recovery strategy, and does not duplicate notifications already received
- [ ] The SSE endpoint requires the same JWT as the backoffice; the client sends it via `fetch` (not bare `EventSource`)
- [ ] The SSE endpoint uses a named event with a structured payload for the RFP ticket, not a single generic message type; tests cover `text/event-stream`, event name, and JSON data shape
- [ ] No calls to a model or agent exist anywhere in this part's implementation
- [ ] Field and entity names match what's defined in your company's `CONTEXT.md`

## 📦 How to Submit This Project

This is Part 1 of 2 of Milestone. Submit it with its own Pull Request against your main branch — don't wait until Part 2 is ready.
1. Commit and push your `feature/sse-notifications` branch (code lives in `services/`, `uis/`, and `tests/` — do *not* create a separate delivery folder)
2. Open a Pull Request describing what you implemented and how to test the SSE stream
3. Include your answers to the Design Questions in the PR description
4. Request a review from your tech lead





# Milestone — Real-Time Systems: WebSocket Chat Streaming (Part 2 of 2)

## README

**Before you start**: read your `CONTEXT-company.md` before writing any code — it defines which agent you're connecting, the chat session fields, and the WebSocket event contract for this part. Part 1 SSE / RFP notification details live under `10-realtime/notification/`, not in this CONTEXT.

## 🎯 Your challenge

📌 You're building on *your copy* of the monorepo for the company you were assigned at the start of the course — not a new repository.

In Part 1 you solved half the problem: the backend tells the frontend when something happens, without anyone having to ask. But that notification only flows one way. Your company's support agent works the same way today: the user sends a message, waits, and gets the full response all at once. If the agent is heading down the wrong path, the user has no way to say so until it finishes responding.

The support team filed an *RFI*: they want to know why the chat doesn't feel like a real conversation. Your tech lead turned it into a *ticket* for your squad:

*Context:* the support agent already exists and works — you won't touch its internal logic or its tools. *What I need you to build:* the agent's response arriving token by token in real time, and the user being able to interrupt it mid-response and redirect it, without waiting for it to finish. *Acceptance criteria:* the channel must be bidirectional (the client also sends data, not just receives), tokens must stream as they're generated, and an interruption must genuinely *abort* the ongoing generation — not just ignore the response once it arrives.

Some requirements are left implicit, and you'll need to identify them carefully: SSE (what you used in Part 1) is no longer enough because the client needs to talk back while the server keeps sending data; token streaming and abort handling need to coexist on the same channel without stepping on each other; and the connection must recover if it drops, just like in Part 1, but now in both directions — reattaching to the same chat thread.

*Out of scope for this part:* you're not building a new agent or changing its tools or memory. The support agent you already have stays the same — what changes is how it communicates with the user.

## 🌱 How to Start the Project

Keep working on the fork of your company's monorepo that you've been using since Milestone (and Part 1 of this milestone). If for some reason you don't have your fork yet, create it now from the base monorepo.

1. Create a new branch from your main branch: `feature/websocket-chat`.
2. Locate the endpoint or function that currently invokes your support agent with a traditional request/response pattern — extend that path; do not create a parallel app or a delivery folder.
3. Check your `CONTEXT-company.md` (under `10-realtime/communication/`) to confirm which agent you're connecting and the chat session / event names for this part — reuse naming *discipline* from Part 1, not Part 1's RFP/SSE schemas.
4. Review how your agent exposes streaming (LangGraph's messages, values, updates, or custom modes) before deciding which one you need to transmit tokens.
5. Implement under the existing layout: WebSocket in `services/`, chat UI in `uis/`, tests in `tests/`.

If you need a refresher on how to set up a project, check out how to start a coding project.

## 💻 What You Need to Do

*Backend (`services/`)*
- [ ] Implement a WebSocket endpoint that accepts a persistent connection per chat session
- [ ] Protect the socket with the *same JWT* used by the backoffice API (and Part 1 SSE). Pass the token on connect via query string (e.g. `?token=…`) and/or a first client auth frame — browsers cannot set Authorization on the WebSocket handshake cleanly. Reject unauthenticated connections before any chat events
- [ ] Require `session_id` (and/or LangGraph `thread_id`) in the handshake / URL so the socket is bound to an existing conversation thread
- [ ] Stream the agent's response token by token over that connection, using whichever LangGraph streaming mode fits
- [ ] On client interrupt: *abort the running stream* so no further `token_chunk` events are produced for that generation (cancel the task / stop the model stream). Do *not* treat LangGraph `interrupt()` HITL as a substitute for stream abort — use `interrupt()` only if you also need a separate graph-level pause
- [ ] After abort: mark the partial assistant message as interrupted (keep tokens already shown), accept new user input, and start a *new* assistant turn — do not delete or overwrite the interrupted message in place
- [ ] Decouple the agent's event production from the WebSocket connections consuming it using a pub/sub pattern — an external backplane like Redis isn't required for this deliverable, but the producer/consumer pattern itself is evaluated

⚠️ *IMPORTANT:* chat field names and entities must match your Part 2 CONTEXT. A generic implementation that ignores the context will not be accepted. Do not mix Part 1 RFP notification payloads into this WebSocket contract.

*Frontend (`uis/`)*
- [ ] Connect the existing chat interface via WebSocket instead of a single request/response call
- [ ] Render the agent's response as tokens arrive (a live typing effect, not swapping in the full message at the end)
- [ ] Add an interrupt control (for example, being able to send a new message while the agent is still responding) that fires the abort signal to the backend; keep the partial message visible and marked interrupted; show the redirected reply as a new message
- [ ] Implement reconnection with progressive backoff: on reconnect, send the same `session_id` / `thread_id` and *rehydrate* the conversation from checkpoint and/or message history before accepting new tokens — "without losing the thread" means restore context, not only reopen a socket

*Testing (`tests/`)*
- [ ] Unit test(s) verifying the WebSocket's event contract (`token_chunk`, `interrupt` / `generation_interrupted`, `generation_completed`)
- [ ] Test, or documented manual verification, that an interrupt mid-response stops further tokens from the original generation, leaves the partial message marked interrupted, and that the next reply is a new turn reflecting new_input
- [ ] Test, or documented manual verification, that reconnect with the same `session_id` restores the conversation thread (history / checkpoint), not an empty chat

## 🤔 Design Questions

Before considering your implementation done, think through and document your answers to these questions in your PR:
- Why does this feature need WebSockets instead of what you built in Part 1? What specifically about the requirement forces a bidirectional channel?
- If more than one client is subscribed to the same chat session (for example, a supervisor watching the conversation live), how do you make sure they all get the same events without duplicating calls to the agent?
- How did you separate *stream abort* (stop tokens) from LangGraph HITL `interrupt()` (graph pause), if you used the latter at all? What happens to the partial assistant message and the next turn?

## ✅ What We Will Evaluate

- [ ] The chat interface shows response tokens as they're generated, not the full response all at once
- [ ] The WebSocket requires the same JWT as the backoffice (query param and/or first-frame auth); unauthenticated clients are rejected
- [ ] The WebSocket is bound to an existing conversation via `session_id` and/or LangGraph `thread_id` in the handshake or URL
- [ ] Sending an interrupt mid-response measurably aborts the original generation (no further tokens), keeps the partial message marked interrupted, and the agent's next response is a new turn that reflects the new input
- [ ] The WebSocket reconnects after a drop with the same `session_id` / `thread_id` and rehydrates from checkpoint or history — conversation thread is not lost
- [ ] Agent event production is decoupled from WebSocket consumers via a pub/sub (or equivalent producer/consumer) pattern; events are named and structured, not a single generic message type
- [ ] Field and entity names match what's defined in your company's Part 2 CONTEXT.md

## 📦 How to Submit This Project

This is Part 2 of 2 of Milestone. Submit it with its own Pull Request against your main branch — independent from Part 1.

1. Commit and push your `feature/websocket-chat` branch (code lives in `services/`, `uis/`, and `tests/` — do *not* create a separate delivery folder)
2. Open a Pull Request describing what you implemented and how to test token streaming and interrupt
3. Include your answers to the Design Questions in the PR description
4. Request a review from your tech lead