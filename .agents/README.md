# `.agents/`

Coding-agent configuration for maintaining the TrackFlow repository.

This folder holds the rules and reusable workflows that coding agents (Claude, Codex, etc.) apply when working in this repo. It is **not** for TrackFlow's product AI agents — for the `.agents/` vs `agents/` vs `skills/` distinction, see the canonical table in `../AGENTS.md`.

## Contents

- `rules/` — scoped development rules agents must apply when the rule's scope matches their work. See `rules/README.md` for the catalog.
- `skills/` — reusable coding-agent workflows for recurring repository maintenance tasks. See `skills/README.md` for the catalog.

## How to use

- Apply any rule in `rules/` whose scope matches the files being touched.
- Use a skill in `skills/` when it fits the task.
- Keep this folder focused on coding-agent behavior for maintaining this repo, not TrackFlow product features.
