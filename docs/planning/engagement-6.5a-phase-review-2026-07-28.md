# Engagement 6.5.a Local Review Evidence — 2026-07-28

## Status

Independent Phase 6.5.a is implemented and locally verified. It is **offline only** and stops here
for owner review; Phase 6.5.b formal evaluation has not started. It was not sequenced behind
Phases 6.1–6.4 and has no production serving surface.

## Dataset and reproducibility

- The planning CSV and generator were relocated first to `data/raw/trackflow_sales.csv` and
  `scripts/generate_trackflow_sales.py`.
- The relocation was byte-preserving. The CSV SHA-256 remains
  `db18966a665e70ea85f5c979c1574b95615520872bab51035d676915284a8433`.
- The relocation hash was recorded before the generator was subsequently hardened in scope to
  reject non-finite numeric values and invalid month sequences. Its review SHA-256 is
  `8d245e2c89ddd5008b6d62b2dd095c96325ba0ec5dad0736734c1a01a00f7950`.
- `python scripts/generate_trackflow_sales.py --check` passes: 120 ordered monthly rows,
  2016-01 through 2025-12, all `consolidated`, internally consistent, fixed seed 42.
- Tests prove regeneration is byte-identical and malformed headers, `NaN` values, and invalid month
  sequences fail loudly.

The dataset is generated, not observed. The deterministic structure is easier to learn than real
revenue, so the reported errors are optimistic; the model card states this plainly.

## Model and artifacts

The fixed Random Forest uses 84 post-lag training rows, 400 trees, seed 42, no holdout-driven
tuning, eight causal calendar/prior-revenue features, and a strict per-tree recursive forecast from
the 2023-12 origin through the 24-month 2024–2025 holdout. Same-month target, shipments, and average
revenue per shipment are excluded.

| Metric | Result |
|---|---:|
| MSE | 4,234,779,297.39 EUR² |
| RMSE | 65,075.18 EUR |
| RMSE / mean test revenue | 9.0318% |
| PSI over predicted revenue | 11.0910 |
| Continuous-target Gini / Somers' D | 0.5000 |
| D'Agostino–Pearson K² | 7.7936 (`p = 0.020307`) |

The versioned model, manifest, metrics, prediction table, model card, and chart live in
`data/eval/`. The chart labels P10–P90 as Random Forest ensemble spread, not a calibrated
prediction interval. Artifact hashes in `sales_forecast_manifest.v1.json` match the regenerated
files.

## Dependency and image isolation

Forecasting packages are optional development/offline dependencies. A recursive AST test starts
from `central_api.main`, `pipelines.business_performance.worker`, and
`scripts.maintenance_worker` and proves their reachable repository import graph does not reach the
forecasting module or any ML package.

Two clean builds used the same Dockerfile/base images. The baseline context preserved the concurrent
Phase 6.1 work and removed only Phase 6.5.a files/dependency metadata.

| Image | Uncompressed size |
|---|---:|
| Pre-6.5.a isolated baseline | 166,021,961 bytes |
| Phase 6.5.a final | 167,182,885 bytes |
| Residual source/artifact delta | 1,160,924 bytes (0.70%) |

The final production virtual environment contains none of `matplotlib`, `numpy`, `scipy`,
`sklearn`, `xgboost`, or `pandas`; the ML dependency contribution is therefore zero. The residual
delta is repository source/artifact and lock metadata copied by the existing broad `COPY data data`.
The approved plan §4.8 identified that literal byte equality is impossible under that Dockerfile
and instructed the implementer not to change Docker or `.dockerignore` without a specification
amendment. Owner review must confirm that “zero ML dependency contribution” satisfies the
specification's otherwise ambiguous “unchanged in size” shorthand.

Direct and relevant transitive package versions/licenses are recorded in
`THIRD_PARTY_LICENSES.md`, including the SciPy wheel's dynamically linked `libquadmath`.

## Local verification

| Gate | Result |
|---|---|
| Focused forecasting tests | 19 passed |
| Full data-pipeline tests + branch coverage | 115 passed; 90.61% |
| Data Ruff | Passed |
| Data strict mypy | Passed, 23 source files |
| Data package build | Passed |
| Generator `--check` | Passed |
| Central API production image build/package probe | Passed |
| Chart visual inspection | Passed |
| Whitespace audit | `git diff --check` passed |

No production database, runtime endpoint, migration, Compose service, or serving code was added for
forecasting.

## Review decision

**Accepted by the owner on 2026-07-28 as an offline evaluation only.** This acceptance does not
approve the model for serving, Finance, staffing, or operational decisions.
