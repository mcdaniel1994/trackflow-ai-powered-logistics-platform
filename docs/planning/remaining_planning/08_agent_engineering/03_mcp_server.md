# MCP Server: Connecting Your Agent to the Company's Tools

## 🎯 The Challenge

### About MCP Servers

An MCP Server exposes a system's capabilities (tools, resources, prompts) through a standard
protocol that any compatible agent can discover and consume, without coupling to your backend's
internal code. Unlike the tools you already wired directly into your agent's graph, an MCP Server
can be reused by multiple clients—other agents, other teams, or other companies in the
ecosystem—as long as they authenticate correctly. That's why authentication and the principle of
least privilege aren't a nice-to-have: an MCP Server without authentication is a real
vulnerability from day one.

Your agent already knows how to call tools directly. Now your tech lead has filed a **ticket**
asking for those capabilities to stop being hardcoded inside the graph and instead be exposed as
an independent, reusable service protected by **OAuth**. The agent itself must also stop calling
the Incidents Manager directly and consume it through the MCP Server instead.

> **From:** Your tech lead
> **To:** Your squad
> **Subject:** RFP — MCP Server for company tools
>
> The agent we built already queries the Incidents Manager from inside the graph, but any future
> integration (another agent, another team, an external partner) would have to reimplement those
> same calls. We need to expose them as an independent **MCP Server**, authenticated with
> **OAuth**, so that any authorized MCP client can:
>
> - Manage Incidents Manager tickets (create, update, and check status).
> - Query—**never edit**—inventory data.
>
> The server must not grant more permissions than strictly necessary for each tool. Document the
> discovery well: any client should be able to understand what the server can do without needing
> additional human context.
>
> And don't leave the migration half-done: I want the agent itself to replace its direct Incidents
> Manager tool with a call to the MCP Server as a client. If the agent is still calling the
> Incidents Manager outside the server, the ticket isn't resolved.
>
> Acceptance criteria are in the checklist. Let me know when it's ready to test from an MCP
> client.

As part of the challenge, your implementation must resolve—without being told explicitly in a
checklist—the following design decisions:

- Which transport to use (`stdio` versus Streamable HTTP) depending on whether the server is
  consumed locally or by multiple remote clients, and what that choice implies for authentication.
- How to structure the permission system so the inventory tool is, by design, read-only. It isn't
  enough to simply not implement the write endpoint; the server must explicitly reject any
  attempt.
- What information to expose in discovery (tool names, descriptions, and schemas) so an external
  agent, with no prior human context, understands what it can and cannot do.
- How to replace, inside the agent's graph, the node that called the Incidents Manager directly
  with tools from the MCP Server through `langchain-mcp-adapters`, without breaking the existing
  routing between RAG and tools.

## 🌱 How to Start the Project

1. Work on top of the Incidents Manager backend and inventory module you already built in previous
   milestones. The MCP Server relies on those services; it doesn't replace them.
2. Install the dependencies you need with `uv add` (for example, `fastmcp`, `mcpauth`, and
   `langchain-mcp-adapters`). Never use `pip install` directly in this monorepo.
3. Create the MCP Server inside the monorepo's `mcps/` folder, not under `services/`.
4. Wire OAuth with MCP Auth (Python package `mcpauth`)—plug-and-play OAuth 2.1/OIDC for MCP
   resource servers. Do **not** rely on FastMCP's built-in authentication helpers; use MCP Auth for
   Protected Resource Metadata, bearer JWT validation, and scopes.
5. Locate the agent node that currently calls the Incidents Manager directly. That's the point
   you'll migrate so it consumes the new MCP Server as a client instead of calling the API outside
   it.

## 💻 What You Need to Do

### MCP Server

- [ ] Implement the MCP Server in Python under `mcps/` using FastMCP or an equivalent MCP SDK.
- [ ] **Implement OAuth authentication with MCP Auth (`mcpauth`)**: mount Protected Resource
  Metadata, validate bearer JWTs against a compliant OAuth 2.1/OIDC provider, and reject
  unauthenticated access. Do **not** use FastMCP's built-in OAuth/authentication layer for this
  project.
- [ ] Expose at least one tool to manage Incidents Manager tickets (create, update, and check
  status).
- [ ] Expose at least one **read-only** tool over inventory. Any modification attempt must be
  explicitly rejected by the server, not simply omitted.
- [ ] Document each tool with a name, description, and input/output schema sufficient for an
  external agent to discover it without additional human context—an MCP-discovery equivalent of
  `--help`.

> **Important:** Field names, entity IDs, and domain-specific values in your implementation must
> match the incident and inventory APIs you already built. A generic implementation that ignores
> your existing services will not be accepted. Status changes must go through the Incidents
> Manager lifecycle endpoint (`PATCH /api/incidents/{id}/status`), not a generic `PATCH` on the
> incident resource. An MCP Server without OAuth through MCP Auth will not be accepted.

### Authentication and security

- [ ] Protect the server with **OAuth through MCP Auth**. No client without a valid access token
  can list or invoke tools. This is mandatory: the MCP Server must not expose company tools
  without authentication. Prefer MCP Auth over FastMCP's built-in authentication so the flow
  matches the MCP authorization specification (resource-server mode, scopes, and
  provider-agnostic OIDC).
- [ ] Apply the principle of least privilege: each tool only has access to the data and operations
  it needs to do its job. Enforce scopes with MCP Auth `required_scopes` where applicable.
- [ ] Define and document the expected error and exit codes for authentication, authorization, or
  validation failures, rather than returning a generic "error."
- [ ] Log every tool invocation—which tool, which client, and what result—for traceability.

### Validation (MCP Playground)

- [ ] First, test your MCP Server in MCP Playground. From **GitHub Codespaces**, expose or forward
  the MCP Server port with public visibility and paste the **Codespaces forwarded URL** into
  Playground. `localhost` alone will not work from that site. Connect, then run at least one
  complete flow per exposed tool.
- [ ] Test and document the server's behavior when a write attempt is made on the inventory tool.
  It must fail in a controlled, explainable way.

### Agent migration

- [ ] Connect the LangGraph agent you already built to the MCP Server using
  `langchain-mcp-adapters`: replace the node that called the Incidents Manager directly with tools
  loaded from the MCP Server.
- [ ] Remove—or explicitly deprecate and stop using—the previous direct tool implementation. The
  agent must not have two possible paths to the Incidents Manager.
- [ ] Confirm that the existing routing between RAG and tools still works the same as before, now
  with the new MCP client node in place of the previous one.

## ✅ What We Will Evaluate

- [ ] The MCP Server lives under `mcps/`, starts correctly, and exposes its tools through the
  standard MCP discovery mechanism.
- [ ] A client without a valid OAuth access token cannot list or execute any tool.
- [ ] The ticket management tool creates, updates status through
  `PATCH /api/incidents/{id}/status`, and queries against the company's real Incidents Manager.
- [ ] The inventory tool responds correctly to queries and explicitly rejects any write operation.
- [ ] Each tool has a clear description and schema, verifiable through the server's own discovery
  without reading the source code.
- [ ] Authentication, authorization, and validation errors return distinct codes and messages.
- [ ] There is at least one log entry per tool invocation with client, tool, and result.
- [ ] The agent no longer calls the Incidents Manager directly; every interaction goes through the
  MCP Server as a client.
- [ ] MCP Playground was exercised using the **public Codespaces forwarded URL**, not `localhost`.

## 📦 How to Submit

Follow the monorepo's standard delivery flow: push your branch, open a pull request against your
fork, and describe in the pull request which transport you chose and why. Let your tech lead know
when the server is ready to be tested from an external MCP client.
