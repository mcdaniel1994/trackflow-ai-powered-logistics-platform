# `agents/`

This folder is for **product AI agents that TrackFlow will ship** — things like a customer support bot, a returns-triage agent, or an internal sales copilot. They are part of upcoming engagements (see the roadmap in the root `README.md`).

> **Not for coding-agent infrastructure.** If you are looking for the rules and workflows that Claude, Codex, or other AI assistants follow while working in this repo, see [`../.agents/`](../.agents/) and [`../AGENTS.md`](../AGENTS.md). The canonical `.agents/` vs `agents/` distinction lives in `../AGENTS.md`.

## Current state

No production product agents have been built yet. The folder currently contains:

- `_template/` — starter pattern for a new agent (README, `agent.py` stub, `tests/`).
- `tools/` — placeholder for reusable tools shared across agents.

## How to add an agent

Each agent lives in its own subfolder named for the agent (for example `support-agent/`, `onboarding-agent/`, `sales-assistant/`). The subfolder's `README.md` should cover:

- **Goal** — what the agent does and for whom
- **Capabilities** — what tasks it handles
- **Knowledge / memory sources** — where its grounding comes from
- **Available tools** — what it can call
- **How to test it**

When a new agent ships, link it from this README so the catalog stays current.
