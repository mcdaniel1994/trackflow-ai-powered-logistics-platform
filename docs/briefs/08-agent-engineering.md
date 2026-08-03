# Brief: Agent Engineering (LangGraph)

## Client: TrackFlow · Stakeholder: Valentina Cruz (Customer Experience Manager)

## Status

🚧 In progress — Engagement 8 Phases 0–2 are committed on `engagement-8-agentic-engineering`;
Phase 3 (OAuth-protected MCP tools) is implemented and awaiting owner review. Phase 4 guardrails
must not begin until that review is complete.

---

## Background

TrackFlow's Engagement 7 knowledge assistant answers policy questions from the company knowledge
base, but customer-experience work also depends on live operational facts. Valentina Cruz's team
supports B2B brands and B2C recipients in the United States and Spain, and needs one assistant that
can choose between policy retrieval and authoritative operational tools without hiding its execution
path or weakening TrackFlow's authentication boundary.

Engagement 8 turns the existing RAG flow into an explicit LangGraph agent, adds auditable live-data
tools through an OAuth-protected MCP server, hardens the agent against prompt injection and policy
mixing, and finally adds human-confirmed structured memory. Guardrails must precede persistent
memory so a one-conversation manipulation cannot become durable agent behavior.

## Stakeholder Request

Valentina Cruz has framed the operational need this way:

> My support team should not have to switch between policy documents, incident tickets, and
> inventory screens to answer routine questions. I need a first-line assistant that can use the
> right source, show us what path it took, and refuse unsafe or unauthorized requests.
>
> It must work for both our US and Spain operations without mixing their policies. If it learns a
> recurring correction, the user must see and approve exactly what will be remembered. No customer
> address, warehouse route, isolated complaint, or active contract negotiation belongs in memory.
>
> The operational tools must be reusable outside this one agent, protected with real OAuth scopes,
> and every call must remain attributable without logging customer data or credentials.

## Assignment

Build a governed Customer Experience agent on the Engagement 7 retrieval functions. Use LangGraph
for explicit routing and traceable nodes, a standalone Streamable HTTP MCP server for incidents and
read-only inventory, TrackFlow Identity for OAuth 2.1 authorization, layered guardrails before
memory, Postgres for safe traces and structured memory, and the Back Office Agent OS for operator
visibility.

Deliver the work in owner-reviewed phases. Each phase must be independently tested and committed;
do not push, deploy, or continue into the next phase without approval.

## What You're Building

### 1. Explicit LangGraph runtime and traces

- Route questions between RAG, live tools, both sources, or rejection.
- Reuse Engagement 7 `retrieve()` and `generate_answer()` rather than duplicating them.
- Persist safe run, node, and tool metadata in self-hosted Postgres; never persist raw prompts,
  retrieved text, tool arguments, credentials, addresses, warehouse routes, or carrier rates.

### 2. Reusable OAuth-protected MCP tools

- A standalone Python project under `mcps/`, using FastMCP Streamable HTTP at `/mcp`.
- OAuth 2.1 Protected Resource Metadata and bearer verification through `mcpauth`, with TrackFlow
  Identity as the authorization server.
- Ticket create, lifecycle-status update, and status lookup tools backed by the existing Incidents
  Manager API.
- Read-only inventory list/detail access with explicit, controlled rejection of every write attempt.
- Delegated user identity, least-privilege scopes, safe per-invocation audit logs, and discovery
  descriptions/schemas sufficient for an external MCP client.

### 3. Guardrails

- Separate system and user authority, detect instruction-change attacks, isolate tool/RAG content,
  block personal-chatbot use, enforce session authorization, prevent US/Spain policy mixing, and
  validate output before returning it.
- Log each structural, content, or security intervention and expose trigger counts.
- Keep build-failing tests for the required jailbreak and injection variants.

### 4. Human-confirmed structured memory

- Consolidate recurring facts by carrier and country in Postgres through an explicit read/write
  interface.
- Propose memorable facts in conversation, require an explicit approve/reject/edit classification,
  allow one pending proposal, default ambiguity to discard, and audit every decision.
- Never store exact B2B/B2C addresses, warehouse routes, isolated incidents, or active commercial
  negotiation data.

### 5. Agent OS observability

- Replace the Back Office `/agent-os` placeholder with run lists and per-run graph traces, tools,
  timings, token/cost metadata, errors, and safe final-output previews.
- Capture model token/cost usage and schedule trace retention pruning.

## Acceptance Criteria

- The graph makes the RAG/tool/both/reject path explicit and every run produces safe queryable trace
  metadata without prohibited content.
- An unauthenticated MCP client cannot discover or invoke tools; wrong issuer/audience/signature and
  insufficient scope fail with distinct, safe errors.
- Ticket creation, lookup, and lifecycle updates use the real Incidents Manager contracts; inventory
  reads use the real inventory contracts and write attempts never reach Central API.
- The LangGraph ticket node has exactly one operational path through MCP and no direct
  `IncidentService` call remains in the agents domain.
- Guardrail tests fail the build if mandated injection variants are obeyed, and authorization plus
  country-policy boundaries are covered.
- Memory writes require explicit human confirmation, respect every never-store rule, consolidate by
  carrier/country, and demonstrate one approved and one rejected full cycle.
- Agent OS renders stored runs and trace details, including captured token/cost data and retention.
- Each phase passes the full Central API suite against disposable PostgreSQL, Alembic model check,
  lint, typing, builds, and every additional touched-project gate before its commit.

## Out of Scope

- Pushing, deploying, opening a pull request, or making paid provider calls without owner approval.
- LangSmith or another hosted tracing platform.
- Direct MCP inventory writes or a second Incidents Manager integration path.
- Production exposure of Identity or MCP before an owner-approved domain, TLS, secrets, rollback,
  and deployment review.
- Persistent memory before the guardrail phase is accepted.
- Multi-agent architecture, autonomous memory approval, or replacing the Engagement 7 RAG stack.
