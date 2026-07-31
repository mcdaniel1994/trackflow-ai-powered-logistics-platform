"""Agent tools — live operational data the agent decides to call (Engagement 8, Part 2).

Unlike the RAG knowledge base (stable policy documents), a tool returns the *current* value from an
authoritative service. Each tool has a typed input/output contract, an explicit timeout, and an
explicit fallback so a tool outage never fabricates a value. Part 3 re-points these at the
OAuth-protected MCP server; the graph nodes stay the same.
"""
