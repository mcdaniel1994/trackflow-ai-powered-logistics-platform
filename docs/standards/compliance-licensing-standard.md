# Compliance & Licensing Standard

**Last reviewed:** July 2026
**Next review due:** October 2026 (quarterly)

## Scope

Applies to every third-party dependency, asset, external service, and AI model/provider brought into
this repo, across every Python (`pyproject.toml`/`uv.lock`) and JavaScript (`package.json`/lockfile)
project, plus the product AI agents in `agents/` and capabilities in `skills/`. It governs license
classification, attribution, and the approval path for non-permissive dependencies.

Secrets, credentials, TLS, and general application security remain governed by
[authentication-security-standard.md](authentication-security-standard.md) and
[production-readiness.md](production-readiness.md) — this standard does not duplicate them. This repo
has no established scope for personal-data processing or a regulated industry (HIPAA, PCI-DSS, FERPA,
etc.); if that changes, extend this standard rather than assuming coverage exists.

## License Categories

| Category | Examples | Commercial use | Action required |
|---|---|---|---|
| Permissive | MIT, BSD-2/3-Clause, ISC, Apache-2.0 | Yes | None beyond attribution; approved by default |
| Weak copyleft | LGPL-2.1/3.0, MPL-2.0 | Yes, conditionally | Acceptable when used unmodified/dynamically linked; must be listed in `THIRD_PARTY_LICENSES.md` |
| Strong copyleft | GPL-2.0/3.0, AGPL-3.0 | Conditional | Repository-owner approval required before adoption |
| Non-commercial | CC-BY-NC-*, evaluation-only licenses | No | Must not be used; find a permissive/paid alternative |
| Proprietary / custom | Vendor EULAs, model-specific community licenses | Per agreement | Read the terms; record the determination in `THIRD_PARTY_LICENSES.md` |
| No license declared | Unlicensed repo, unattributed snippet | Assume all-rights-reserved | Must not be used without obtaining an explicit license |

## Default Policy

- This repo's own code is proprietary: the root [`LICENSE`](../../LICENSE) declares All Rights Reserved.
  Every manifest's `license` field must match that (`"UNLICENSED"` for npm packages,
  `license = { text = "Proprietary" }` for Python `pyproject.toml` — PEP 639 validates a bare string as
  an SPDX expression, so the table form is required).
- Permissive dependencies are approved by default.
- Weak-copyleft dependencies (e.g. the `psycopg2-binary` / `psycopg[binary]` LGPL Postgres drivers
  already in use) are acceptable as unmodified, dynamically-linked dependencies, provided they are
  documented in [`THIRD_PARTY_LICENSES.md`](../../THIRD_PARTY_LICENSES.md).
- Strong copyleft, non-commercial, custom-licensed, and unlicensed dependencies require explicit
  repository-owner approval before adoption. Treat "no license found" as all-rights-reserved and do not
  use the resource until a license is obtained.

## Attribution

- `THIRD_PARTY_LICENSES.md` at the repo root is the single register of every dependency that is not
  permissively licensed (permissive dependencies are covered in bulk by re-running `pip-licenses` /
  `license-checker`, not enumerated individually). Update it whenever a non-permissive dependency is
  added, removed, or changes license across a version bump.
- Every manifest's `license` field must stay consistent with the root `LICENSE`. A manifest declaring a
  different license than the repo (e.g. a stray `"MIT"`) is a defect — fix it, don't work around it.

## Dependency Workflow

When adding, upgrading, or removing a dependency, third-party asset, API/SDK integration, or AI
model/provider:

1. **Identify** — name, version, publisher, source URL, and type.
2. **Verify the license** — locate the license file, SPDX identifier, or terms of service. No license
   found → stop, do not use, escalate to the repository owner if there's a real need.
3. **Check commercial rights** — confirm the license permits commercial use, redistribution, and
   modification as this project requires. Non-commercial or unclear → stop, escalate.
4. **Check transitive dependencies** — a dependency's sub-dependencies carry their own licenses;
   periodically re-scan the full tree with `pip-licenses` (Python) or `license-checker` (npm), not just
   top-level manifests.
5. **Record attribution** — add non-permissive dependencies to `THIRD_PARTY_LICENSES.md` with license,
   version, direct/transitive status, and a link to the license text.
6. **Escalate if unresolved** — copyleft (GPL/AGPL/LGPL/MPL), non-commercial, custom-licensed, or
   unlicensed resources require repository-owner sign-off before merging. Permissive dependencies do
   not require prior approval as long as step 5 is done.

## Supply-Chain Baseline

- Lockfiles (`uv.lock`, `package-lock.json`) are committed and kept in sync with manifests.
- Install only from official registries (PyPI, npm); do not add packages from unverified sources or
  unvetted GitHub tarballs.
- Run `pip-audit` / `npm audit` (or equivalent) before release and add findings to the applicable
  release checklist in [production-readiness.md](production-readiness.md).
- Run a full dependency/license audit (all manifests, transitive trees, and `THIRD_PARTY_LICENSES.md`
  reconciliation) at least annually, and before any major release.

## AI Models and Providers

Model and API-provider terms are separate from code licenses and are not covered by an OSS license at
all — they're governed by the provider's terms of service and usage policy. Before adopting a new model
or provider in `agents/`, `skills/`, or product code:

- Confirm the license/terms explicitly permit commercial use for this product.
- Check data-handling terms — whether the provider logs, retains, or trains on submitted data — and
  note any opt-outs taken.
- Record the provider, model, terms version, and date reviewed in `THIRD_PARTY_LICENSES.md`.

## Exceptions

Follow the standard exception mechanics defined in [`docs/standards/README.md`](README.md#exceptions):
state the requirement, why compliance is infeasible, the safest alternative considered, get explicit
repository-owner approval before merging, and record the rationale in the PR description. Silent
non-compliance is a defect, not an exception.
