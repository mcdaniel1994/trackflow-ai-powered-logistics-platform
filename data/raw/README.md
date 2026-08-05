# `data/raw` folder

This folder is intended for **raw data** related to the company: dumps, exports, sample files, event samples, or untransformed datasets.

- **Main purpose**: serve as a landing zone or reference for original data before pipelines process it.
- **Recommendation**: document each dataset’s origin, format, expected size, privacy/PII considerations, and how it is versioned (ideally avoiding sensitive data in the repository).

## `trackflow_sales.csv`

This 120-row consolidated monthly revenue dataset covers 2016-01 through 2025-12 and contains no
PII. It is generated rather than observed: the owner approved that explicit deviation because the
assignment's claimed source file did not exist and production has no revenue dimension. Regenerate
or validate it deterministically with `scripts/generate_trackflow_sales.py` (seed 42).

## `rfp/` — Engagement 9 seed RFP documents

Three fictional sample documents for the RFP agentic workflow (Engagement 9). All content is invented
for testing and contains **no real PII, addresses, or commercial terms** — client names, volumes, and
contacts are fabricated and use `example.com`/`example` domains.

| File | Kind | Country / currency | Expected routing |
|---|---|---|---|
| `luna-cosmetics-us-full.md` | Valid RFP (full scope) | US / USD | `warehouse` + `lastmile` |
| `zaragoza-modaviva-es-partial.md` | Valid RFP (partial scope) | ES / EUR | `warehouse` + `reverse` (no `lastmile`) |
| `not-an-rfp-carrier-pitch.md` | Inbound vendor pitch — **not** an RFP | n/a | classifier must `discard` |

These are the canonical **source texts**. Real RFPs arrive as PDFs; Phase 1 (intake) adds the
PDF→Markdown conversion path and small PDF fixtures rendered from these texts so the converter and
classifier can be exercised end to end. Format: Markdown, a few KB each.
