# MCP Owner-Review Evidence — 2026-08-03

## Scope

This record covers a disposable local Docker exercise exposed through temporary Cloudflare Quick
Tunnels on August 3, 2026 (America/Chicago). It did not use production credentials, production data,
paid provider calls, live-provider evaluations, or Qdrant re-indexing. It was not run in GitHub
Codespaces and therefore does not complete the Phase 3 Codespaces MCP Playground gate.

Cloudflare Workers AI Playground and the official MCP Inspector were used as external clients. This
file records only pass/fail outcomes and safe error types; it intentionally excludes OAuth tokens,
client secrets, tool arguments, tool responses, prompts, customer data, and provider payloads.

## Evidence

| Check | Outcome |
|---|---|
| Public Identity authorization-server metadata and JWKS | Pass |
| Public MCP liveness, readiness, and protected-resource metadata | Pass |
| Unauthenticated MCP request | Pass — rejected with `401` |
| Cloudflare Workers AI Playground tool discovery | Pass — exactly four approved tools |
| Cloudflare model-driven tool invocation | Not executed — Cloudflare returned inference rate-limit `3021` before a tool call |
| Official MCP Inspector PKCE authorization | Pass |
| Inspector tool discovery | Pass — exactly `ticket_check_status`, `ticket_create`, `ticket_update_status`, and `inventory_access` |
| Approved test-ticket creation and status read | Pass |
| Allowed test-ticket lifecycle transitions | Pass |
| Inventory list and single-item read | Pass |
| Controlled inventory delete attempt | Pass — rejected locally with `INVENTORY_READ_ONLY` |
| Central API inventory delete isolation | Pass — no inventory delete request reached Central API |
| Ticket creation without `incidents:write` | Pass — rejected with `INSUFFICIENT_SCOPE` |

## Compatibility Observation

Cloudflare Workers AI Playground omitted the OAuth `resource` value from dynamic client
registration. TrackFlow Identity correctly rejected that request under its strict registration
contract. To finish the disposable local exercise, the running Identity container received a
temporary compatibility shim that supplied only the exact public TrackFlow MCP resource when the
field was absent. The Inspector exercise ran while that shim was active, so this session did not
independently establish whether the Inspector sends the field. The shim was never applied to the
repository or an image, and the container was removed after testing.

This workaround is not evidence that the unmodified dynamic-registration path interoperates with
those clients. The Codespaces runbook's explicit public-client registration with an exact callback
and resource remains the authoritative Phase 3 procedure.

## Cleanup

- Both temporary Cloudflare Quick Tunnels were stopped and deleted.
- The MCP Inspector process was stopped and its TrackFlow OAuth state was deleted.
- Temporary OAuth scripts, response files, cookies, and the Compose override used for the public
  test were deleted from the system temporary directory.
- The disposable TrackFlow Compose stack was removed, which also removed the container-only shim.
- The pre-existing `tf-qdrant` container was disconnected from the temporary Compose network but
  remained running; it was not re-indexed or otherwise mutated.

## Remaining Gate

The Phase 3 Codespaces MCP Playground exercise still lacks Codespaces-specific owner evidence and
remains unverified. Phases 4–6 continue to await owner review.
