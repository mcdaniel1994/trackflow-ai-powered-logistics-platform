# `mcps/`

Standalone Streamable HTTP MCP service for TrackFlow product agents and approved external clients.

The service exposes its transport at `/mcp`, public liveness/readiness probes, and RFC 9728 protected-resource
metadata. TrackFlow Identity issues all bearer tokens. The MCP process validates those tokens with `mcpauth`,
then exchanges the delegated token for a Central API audience token before calling incidents or inventory APIs.

No token, prompt, tool argument, description, address, warehouse detail, carrier rate, or upstream response may be
logged. Invocation logs contain only client ID, subject UUID, tool name, outcome, safe error code, and duration.

## Local commands

```bash
uv run --project mcps uvicorn trackflow_mcp.main:app --reload --port 8004
uv run --project mcps --extra dev pytest
uv run --project mcps --extra dev ruff check .
uv run --project mcps --extra dev mypy trackflow_mcp tests
uv build --project mcps
```

Runtime configuration and the end-to-end Codespaces authorization walkthrough are documented in
[`docs/agents/mcp-codespaces-runbook.md`](../docs/agents/mcp-codespaces-runbook.md).
