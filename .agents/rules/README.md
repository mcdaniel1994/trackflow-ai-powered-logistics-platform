# `.agents/rules/`

Scoped development rules for coding agents working in this repo. Apply any rule whose scope matches the files being touched.

## Catalog

| Rule | Scope | Summary |
|---|---|---|
| `preserve-delivered-engagements.md` | Always active | Do not rewrite delivered stakeholder briefs or delivered app behavior without confirmation. Covers `docs/briefs/`, `docs/archive/`, `docs/standards/visibility.md`, `apps/marketing-site/`, `apps/talent-pipeline-tracker/`, and `packages/shared/`. |
| `public-ui-visibility.md` | File-pattern: `apps/marketing-site/**`, `uis/website/**`, any folder with public-facing pages | Read `docs/standards/visibility.md` sections 1-6 before the change. Verify one H1, `<html lang>`, canonical, OG, Twitter Card, and parseable JSON-LD. |

## Adding a new rule

Each rule file must declare:

- **Rule Name**
- **Scope** (always active, or file-pattern based)
- **Required Behavior**
- **Examples** and **Non-Examples** when scope is file-pattern based

After adding a rule, list it in the catalog above with a one-line summary so agents can decide whether to load it.
