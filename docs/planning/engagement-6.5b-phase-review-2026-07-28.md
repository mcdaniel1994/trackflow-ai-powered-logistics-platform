# Engagement 6.5.b Local Review Evidence — 2026-07-28

## Status

Phase 6.5.b formal evaluation is implemented and locally verified. Engagement 6.5 stops here for
the specification's final owner-review gate. No serving surface, production dependency, deployment,
or operational approval was added.

The accepted Phase 6.5.a holdout and artifact hashes remain reproducible. Cross-validation and the
learning curve use only the 96 source months in the 2016-01 through 2023-12 training partition; the
2024–2025 holdout is never used for diagnosis.

## Five chronological folds

`TimeSeriesSplit(n_splits=5)` creates expanding prefixes followed by disjoint 16-month validation
windows. Each fold rebuilds lag features and the estimator locally, then recursively forecasts its
validation window.

| Fold | Train source / post-lag | Validation dates | Train MAE / RMSE | Validation MAE / RMSE |
|---:|---:|---|---:|---:|
| 1 | 16 / 4 | 2017-05 → 2018-08 | 30,433 / 35,159 EUR | 29,210 / 47,034 EUR |
| 2 | 32 / 20 | 2018-09 → 2019-12 | 12,848 / 18,358 EUR | 50,646 / 64,281 EUR |
| 3 | 48 / 36 | 2020-01 → 2021-04 | 10,834 / 14,208 EUR | 26,831 / 31,323 EUR |
| 4 | 64 / 52 | 2021-05 → 2022-08 | 10,159 / 12,198 EUR | 35,878 / 42,804 EUR |
| 5 | 80 / 68 | 2022-09 → 2023-12 | 10,592 / 13,173 EUR | 56,487 / 65,925 EUR |

Population standard deviation (`ddof=0`) is used because these are the complete five predeclared
folds:

- Training MAE: **14,973 ± 7,785 EUR**.
- Training RMSE: **18,619 ± 8,532 EUR**.
- Validation MAE: **39,810 ± 11,763 EUR**.
- Validation RMSE: **50,273 ± 13,165 EUR**.

The validation RMSE coefficient of variation is 26.2%; temporal performance is not stable enough
for operational use.

## Diagnosis and corrective action

**Classification: overfitting.** Training RMSE falls from 35,159 to 13,173 EUR as the
chronological prefix grows, while validation RMSE oscillates and ends at 65,925 EUR. The final
train/validation gap is 52,752 EUR and the curves do not converge.

The suspected root cause is bounded tree extrapolation on absolute revenue levels and lag values:
the Random Forest fits observed levels but cannot project the generator's continuing compound
trend beyond learned leaves.

The specific corrective action is to forecast year-over-year revenue growth
(`revenue_t / revenue_t-12 - 1`) with the same chronological protocol, then recursively reconstruct
revenue levels. This targets the identified extrapolation failure rather than generically adding
data or complexity.

RMSE is primary because large peak-season misses carry disproportionate staffing/capacity risk.
MAE remains the companion measure of a typical monthly EUR miss.

## Specification ambiguity recorded

The specification anticipated little or no PSI because the generator has no regime change. The
accepted predicted-revenue PSI is actually **11.0910 (significant)**. The formal report does not
repeat the false anticipated result: later generated revenue levels and bounded Random Forest
extrapolation shift the prediction distribution. Whether stable or significant, PSI on this
generated dataset is not evidence of real-world regime change or robustness.

## Artifacts and reproducibility

- `data/eval/evaluation_report.md`
- `data/eval/sales_forecast_evaluation.v1.json`
- `data/eval/sales_forecast_learning_curve.v1.png`
- `data/eval/sales_forecast_evaluation_manifest.v1.json`

The evaluation manifest records:

- accepted Phase 6.5.a manifest SHA-256:
  `5dab48f315c4e4e9af6c2d1fcaab6d56a22b1f54aad5bfa4bc4703ffce72d377`;
- evaluation JSON SHA-256:
  `34f14b4df39791afe2a4a7ca8411ac70bf8280af802cfbca4ef6899ab3f55e02`;
- learning-curve SHA-256:
  `b6d98dd26340e7febfdb4688a2836f4db44d3c45efbee13f8cd110b9f337a7bb`;
- report SHA-256:
  `601f3ccc4137869900f8a33d36e34b07c2035fa96d5bf7674e1ff699622d43dd`.

The test suite runs the complete train/evaluate command twice and proves every output byte is
identical.

## Production dependency isolation

| Image | Uncompressed size |
|---|---:|
| Accepted Phase 6.5.a | 167,182,885 bytes |
| Phase 6.5.b | 167,488,515 bytes |
| Evaluation source/artifact delta | 305,630 bytes (0.18%) |

The Phase 6.5.b image virtual environment contains none of `matplotlib`, `numpy`, `scipy`,
`sklearn`, `xgboost`, or `pandas`. ML dependency contribution remains zero. The recursive
production import-graph test still proves no production root reaches forecasting or ML modules.

## Quality gates

| Gate | Result |
|---|---|
| Full data-pipeline pytest + branch coverage | 118 passed; 90.47% |
| Focused forecasting tests | 22 passed |
| Ruff | Passed |
| Strict mypy | Passed, 26 source files |
| Data package build | Passed |
| Data lockfile check | Passed |
| Artifact JSON validation | Passed |
| Learning-curve visual inspection | Passed |
| Central API production image build/package probe | Passed |
| Whitespace audit | `git diff --check` passed |

The formal report includes the generated-data limitation, deterministic optimism, 96-month
training bound, PSI contradiction, uncalibrated ensemble-spread warning, and explicit prohibition
on serving or operational decisions.

## Review decision

**Accepted by the owner on 2026-07-28 as the final Engagement 6.5 evaluation gate.** Engagement
6.5.a–b is complete. The overfitting diagnosis and corrective recommendation are accepted as
experiment findings; the trained model remains explicitly unapproved for serving or operational
decisions.

Proposed commit message: `Engagement 6.5: add offline sales forecasting evaluation`.
