# `skills/`

This folder is for **reusable capabilities that TrackFlow product agents call** — for example, a code-review skill, a data-analysis skill, or a research skill consumed by the agents in [`../agents/`](../agents/). They will be built out across future engagements.

> **Not for repo-maintenance workflows.** If you are looking for workflows that Claude, Codex, or other AI assistants follow while working in this repo (for example `start-engagement`), see [`../.agents/skills/`](../.agents/skills/). The canonical `skills/` vs `.agents/skills/` distinction lives in [`../AGENTS.md`](../AGENTS.md).

## Current state

The subfolders here are scaffolding placeholders. None of them define an active product skill yet — each contains a `README.md` (and in some cases stub assets), but no `SKILL.md` is in place.

- `_template/` — starter pattern (with a `SKILL.md` template, `examples/`, `resources/`, `scripts/`) for new skills.
- `code-review/` — placeholder.
- `data-analysis/` — placeholder. Contains stub assets in `resources/` and `scripts/`.
- `research/` — placeholder.

These will be filled in as later engagements need them.

## How to add a skill

Copy `_template/` to a new folder named for the skill, then fill in `SKILL.md` so it answers:

- **When to use** the skill
- **Expected inputs and outputs**
- **Examples**
- **Acceptance criteria**

Keep each skill in its own subfolder so capabilities stay easy to discover.
