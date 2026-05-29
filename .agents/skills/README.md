# `.agents/skills/`

Reusable coding-agent workflows for recurring repository maintenance tasks. Use a skill here when its objective matches the task at hand.

These are **not** TrackFlow product skills. For product capabilities consumed by shipped agents, see `../../skills/` (and the canonical distinction in `../../AGENTS.md`).

## Catalog

| Skill | Objective |
|---|---|
| `start-engagement/` | Initialize a new engagement `NN-<slug>` coherently across the brief, the README roadmap, `docs/briefs/README.md`, `CLAUDE.md`, `memory-bank/progress.md`, and the deliverable folder scaffold. |

> `start-engagement` accepts either structured metadata or a long stakeholder summary (email, meeting notes, etc.); it extracts the required fields and produces a full stakeholder brief, not just a placeholder.

## How agents invoke a skill

These skills are **not** auto-discovered by Claude Code or Codex from this path — those tools load skills from `~/.claude/skills/` or project `.claude/skills/`. In this repo, agents are pointed here by `AGENTS.md`. When a task matches a skill's frontmatter `description`, read that skill's `SKILL.md` end-to-end and follow the workflow before acting.

## Adding a new skill

Create `skill-name/SKILL.md` starting with YAML frontmatter:

```yaml
---
name: skill-name
description: Use when <trigger condition>. <One-sentence summary of what the skill produces.>
---
```

Then the body sections:

- **Objective**
- **Required Inputs**
- **Workflow** (numbered steps)
- **Expected Output**
- **Acceptance Criteria**
- **Verification Method**

After adding, list the skill in the catalog above with a one-line objective.
