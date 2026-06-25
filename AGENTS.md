# Agent Operating Guide

This is the cross-agent operating guide for TrackFlow. Every coding agent working in this repository must follow it before planning, editing, or committing.

## Startup Reading List

Read these at the start of every session, before any action:

1. `memory-bank/projectbrief.md`
2. `memory-bank/techContext.md`
3. `memory-bank/progress.md`
4. `AGENTS.md`
5. `README.md`

Claude-specific sessions also read `CLAUDE.md` after this file.

## Pre-Implementation Reading

Before implementation, read the active engagement brief at `docs/briefs/NN-<slug>.md` and the README for every folder being modified. If public-facing pages are touched, read `docs/standards/visibility.md` and follow sections 1-6. If auth, session, token, cookie, authorization, or AI-agent user-context behavior is touched, read `docs/standards/authentication-security-rule.md`. If you add or change behavior in code, APIs, validation, failure paths, logging, or CI/deploy config, read the relevant engineering-quality standard (`docs/standards/testing.md`, `error-handling.md`, `observability.md`, `production-readiness.md`) and apply `.agents/rules/testing-error-handling-ci.md`.

## Mandatory Pre-Commit Workflow

1. Confirm the engagement brief and acceptance criteria for the change in flight.
2. Run `type-check`, `build`, `lint`, and the tests for every touched package or app, and meet the release gates in `docs/standards/production-readiness.md` (tests pass, coverage preserved, failure paths handled, no sensitive data logged).
3. Update the engagement-tracking docs that move together: `README.md` roadmap row plus "What's Been Built", `docs/briefs/README.md` index, the engagement brief's `## Status`, `CLAUDE.md` "Where New Engagement Code Goes", `memory-bank/progress.md`, and the deliverable folder's README.
4. Verify no protected files were modified outside the engagement scope.
5. Write a commit message naming the engagement.

## Protected Paths

**Do not rewrite delivered stakeholder briefs or delivered app behavior without confirmation. Status/path corrections, required engagement index updates, and integration-only package metadata updates are allowed when they are part of the active engagement cleanup.**

This rule covers:

- `docs/briefs/`
- `docs/archive/`
- `docs/standards/visibility.md`
- `packages/shared/`

## Preserving Milestone Work

Delivered engagements stay intact. New work goes into new folders such as `uis/`, `services/`, or the future engagement home named by the active brief unless an explicit migration decision is documented in that brief.

When delivered code is retired (as the Engagement 1 and 3 standalone apps were in June 2026), the history is preserved through a retirement note in `docs/archive/` and git history — not by keeping dead code on disk. Retirement notes name the replacement path; do not recreate retired code.

## Repository Boundaries

- `apps/` and `uis/` depend on `packages/`; never the reverse.
- Public-facing pages must comply with `docs/standards/visibility.md` sections 1-6 before merge.
- Authentication, authorization, sessions, cookies, tokens, and AI-agent user context must comply with `docs/standards/authentication-security-rule.md`.
- APIs and backend services go under `services/`.
- Code that adds or changes behavior must meet the engineering-quality standards in `docs/standards/` (testing, error-handling, observability, production-readiness) before merge.
- Product AI agents go under `agents/`; reusable product capabilities for those agents go under `skills/`.

## Coding-Agent Infrastructure Vs. Product Agents

This table is the canonical reference for the `.agents/` vs `agents/` vs `skills/` distinction. Other files in the repo (`CLAUDE.md`, `.agents/README.md`, etc.) link here instead of duplicating it.

| Folder | Audience | Purpose |
|---|---|---|
| `.agents/` | Coding agents working in this repo | Configuration: scoped rules + reusable workflows (skills) for how to maintain this codebase |
| `.agents/skills/` | Coding agents | Reusable repo-maintenance workflows (e.g. `start-engagement`) |
| `agents/` | TrackFlow customers / operations | Product AI agents the company ships in later engagements (e.g. support bot, returns triage) |
| `skills/` | TrackFlow product agents | Reusable product capabilities those agents call (e.g. code-review, data-analysis, research) |

## `.agents/` Rules And Skills

- Apply any rule in `.agents/rules/` whose scope matches the files being touched.
- When a task matches the frontmatter `description` of a skill in `.agents/skills/<name>/SKILL.md`, read it end-to-end and follow the workflow before acting.
- Keep `.agents/` focused on coding-agent behavior for maintaining this repo, not TrackFlow product features.
