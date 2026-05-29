# Public UI Visibility

## Rule Name

Public UI Visibility

## Scope

File-pattern based.

## Applies When

Any change touches `apps/marketing-site/**`, `uis/website/**`, or any future folder containing public-facing pages.

## Required Behavior

- Before producing the change, read `docs/standards/visibility.md`.
- The change must comply with sections 1-6: semantic HTML, WCAG 2.1 AA, SEO metadata, GEO formatting, E-E-A-T, and Schema.org JSON-LD.
- Verify one H1 per page, `<html lang>`, canonical link, Open Graph metadata, Twitter Card metadata, and parseable JSON-LD.
- Prefer native HTML elements over ARIA when a native element fits.
- Do not use decorative-only ARIA where semantic HTML or `aria-hidden` on decoration is enough.

## Examples

- Adding a marketing page.
- Editing the lead-capture form.
- Changing `<head>` metadata.

## Non-Examples

- Edits to backoffice views.
- Edits to an internal API surface.
- Edits to `packages/shared` source.
