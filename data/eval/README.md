# `data/eval` folder

This folder is for **evaluation and validation**: evaluation datasets, golden sets, experiment results, metrics, and artifacts used to measure quality for models, RAG, agents, or pipelines.

- **Main purpose**: centralize evaluation inputs and outputs so improvements stay measurable across project milestones.
- **Recommendation**: document each evaluation set (what it measures, how it was built, success criteria) and avoid sensitive data; use synthetic or anonymized data when needed.

## Engagement 6.5 sales forecast

The versioned `sales_forecast_*` artifacts are produced by
`scripts/train_sales_forecast.py`. The manifest records the input hash, fixed seed, split,
predeclared feature and estimator contracts, package versions, and artifact hashes. The prediction
chart's P10–P90 shading is Random Forest ensemble disagreement, not a calibrated interval. The
pickle is a trusted local build artifact and must never be loaded from an untrusted source.

Phase 6.5.b adds `sales_forecast_evaluation.v1.json`, the chronological learning curve,
`evaluation_report.md`, and a separate evaluation manifest. Five expanding-window folds use only
the 2016–2023 training partition. The report diagnoses overfitting, records validation RMSE
50,273 ± 13,165 EUR using population standard deviation, and explicitly rejects serving or
operational use.

Run locally with the isolated optional dependency group:

```bash
uv run --project data --extra forecasting python scripts/train_sales_forecast.py --evaluate --force
```
