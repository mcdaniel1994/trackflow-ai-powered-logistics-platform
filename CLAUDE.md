# Claude-Specific Orientation

Claude-specific orientation for AI coding agents working in this repo. For the cross-agent operating rules every agent must follow, read `AGENTS.md` first.

Claude sessions should read, in order:

1. `memory-bank/projectbrief.md`
2. `memory-bank/techContext.md`
3. `memory-bank/progress.md`
4. `AGENTS.md`
5. `README.md`
6. `CLAUDE.md`

Then read the active engagement brief and the README for every folder being modified.

## Repo Navigation

| If you're looking for... | Go here |
|---|---|
| Cross-agent operating rules | `AGENTS.md` |
| Persistent project context | `memory-bank/` |
| What this project is | `README.md` |
| Current engagement brief when assigned | `docs/briefs/NN-title.md` |
| All briefs | `docs/briefs/` |
| Cross-cutting standards and guidance | `docs/` |
| Archived planning artifacts | `docs/archive/` |
| Coding-agent scoped rules and skills | `.agents/` |
| Forward-looking UI workspace | `uis/` |
| Future backend services and APIs | `services/` |
| Engagement 1 surface (original app retired June 2026) | `uis/website/` + `docs/archive/marketing-site-retirement.md` |
| Engagement 3 tracker (standalone app retired June 2026) | `uis/backoffice/app/talent/` + `docs/archive/talent-pipeline-tracker-retirement.md` |
| Shared TypeScript code | `packages/shared/` |
| Non-code shared resources | `resources/` |
| Product AI agents | `agents/` |
| Data pipelines | `data/` |
| Workflow automations | `workflows/` |
| Product agent capabilities | `skills/` |
| Repo-wide scripts and utilities | `scripts/` |

## Where New Engagement Code Goes

- **Engagement 1** - delivered in `apps/marketing-site/`  
  Built; code retired June 2026. Surface lives at `uis/website/` — see `docs/archive/marketing-site-retirement.md`.

- **Engagement 2** - `packages/shared/`  
  Built.

- **Engagement 3** - delivered in `apps/talent-pipeline-tracker/`  
  Built; code retired June 2026. Now at `uis/backoffice/app/talent/` — see `docs/archive/talent-pipeline-tracker-retirement.md`.

- **Engagement 4** - `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, `services/`  
  Built.

- **Engagement 5+** - TBD per engagement.  
  Confirm with Cory before placing new code.

## Coding-Agent Infrastructure Vs. Product Agents

For the `.agents/` vs `agents/` vs `skills/` distinction, see the canonical table in `AGENTS.md`.

## Claude Notes

- Prefer `rg` and `rg --files` for searches.
- Before public-facing UI work, read `docs/standards/visibility.md` and apply the matching `.agents/rules/public-ui-visibility.md` rule.
- Before auth, session, token, cookie, authorization, or AI-agent user-context work, read `docs/standards/authentication-security-rule.md` and apply the matching `.agents/rules/authentication-security.md` rule.
- Empty folders with READMEs are intentional scaffolding for future engagements.
