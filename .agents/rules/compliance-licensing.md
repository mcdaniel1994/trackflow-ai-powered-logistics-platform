# Compliance & Licensing

## Rule Name

Compliance & Licensing

## Scope

File-pattern and task based.

## Applies When

- Adding, upgrading, or removing a dependency in any manifest (`pyproject.toml`, `package.json`,
  `uv.lock`, `package-lock.json`).
- Adding a new third-party API, SDK, or external service integration.
- Adding or changing an AI model or provider integration (`agents/`, `skills/`, or product code).
- Editing `LICENSE` or `THIRD_PARTY_LICENSES.md`.
- Any explicit dependency, license, or compliance audit request.

## Required Behavior

- Before making the change, read
  [`docs/standards/compliance-licensing-standard.md`](../../docs/standards/compliance-licensing-standard.md).
- Treat that standard as the source of truth for license classification, attribution, and third-party
  dependency approval.
- Update `THIRD_PARTY_LICENSES.md` and the relevant manifest `license` field whenever the dependency set
  or licensing status changes.
- Escalate to the repository owner before adopting a copyleft (GPL/AGPL/LGPL/MPL), non-commercial,
  custom-licensed, or unlicensed dependency, or an AI model/provider with unclear commercial terms.
- Do not duplicate the standard's content here — this rule only routes to it.

## Examples

- Adding a new npm or PyPI package.
- Integrating a new AI model or provider.
- Vendoring a font, icon set, or media asset.
- Running a full dependency/license audit.

## Non-Examples

- A version bump of an already-approved permissive dependency with no license change.
- Copy or documentation edits that merely mention a dependency without changing a manifest.
