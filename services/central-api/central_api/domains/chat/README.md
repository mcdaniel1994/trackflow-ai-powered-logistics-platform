# Chat persistence domain

Engagement 10 Phase 3 stores owner-scoped chat sessions and user-visible messages in PostgreSQL.
`chat_sessions.session_id` is the WebSocket session identifier and LangGraph thread id;
`chat_messages` is ordered by a database-enforced per-session sequence.

The repository exposes only bounded, owner-filtered reads. Deleting a session cascades to its
messages, which lets the maintenance worker enforce the approved 90-day retention window in bounded
batches. Message content is product history, not telemetry: it must never be copied into agent
traces, logs, error responses, or analytics.

Phase 3 added persistence only; transport, session APIs, and the Back Office UI were deferred to
later owner-gated phases.

Phase 4 adds authenticated `POST/GET /chat/sessions` and owner-filtered detail reads. Creating a
session also reserves the same UUID in `agent_conversations`, so the existing HTTP agent endpoint
can provide multi-turn memory while persisting user/assistant messages into chat history. Chat turns
always suppress trace input/output summaries, even if general agent content capture is enabled. The
current Identity token has no tenant claim, so the owner-only portfolio deployment provisionally
uses the authenticated `user_id` as `client_id`; an external-user rollout must replace that mapping
with an authoritative tenant/client claim.

The manual route preference only bypasses the existing classifier; it does not add or alter an
agent or tool.

Phase 5 adds one application-scoped generation manager and the owner-bound
`/realtime/chat/{session_id}` socket. A session has at most one active provider generation even when
multiple sockets subscribe. Each connect subscribes before reading the authoritative snapshot, so
events cannot fall into the snapshot/reconnect gap; a reconnect during generation also receives the
owner-checked active partial answer and its last sequence before later queued deltas. The manager
publishes persisted user messages, guarded answer deltas, and terminal completion/interruption
events through `chat.<session_id>`.
Interrupt sets the provider cancellation signal, waits for the stream to close, persists a nonempty
partial assistant message with `interrupted=true`, and only then starts optional redirected input.

Phases 3–5 are implementation-complete and merged to `main` through PR #36. Phase 6 production
migration, deployment, and feature enablement are deferred.
