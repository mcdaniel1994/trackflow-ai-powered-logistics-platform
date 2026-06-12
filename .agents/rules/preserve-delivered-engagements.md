# Preserve Delivered Engagements

## Rule Name

Preserve Delivered Engagements

## Scope

Always active.

## Required Behavior

**Do not rewrite delivered stakeholder briefs or delivered app behavior without confirmation. Status/path corrections, required engagement index updates, and integration-only package metadata updates are allowed when they are part of the active engagement cleanup.**

This rule covers:

- `docs/briefs/`
- `docs/archive/`
- `docs/standards/visibility.md`
- `packages/shared/`

Delivered milestones remain intact unless an active engagement brief explicitly documents a migration or behavior change.

Retired delivered code (e.g. the Engagement 1 and 3 standalone apps deleted in June 2026) is preserved through retirement notes in `docs/archive/` and git history, not on-disk copies. Do not recreate retired code; follow the replacement paths named in the retirement notes.
