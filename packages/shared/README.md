# `packages/shared/`

Shared TypeScript types and utilities used across the monorepo (`apps/`, `agents/`, etc.).

**Current status:** Scaffolding. Real implementations land in Engagement 2.  
See `docs/briefs/02-inventory-carriers.md` for the stakeholder brief.

- Consumed by other packages via `@repo/shared-types` (see `package.json`)
- Never import from `apps/` or `agents/` into this package — dependency flows one direction only