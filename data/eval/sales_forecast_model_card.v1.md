# TrackFlow Sales Forecast — Phase 6.5.a Model Card

## Scope and provenance

This is an offline feasibility artifact, not a production forecast or serving contract. The source
CSV is generated rather than observed. The owner approved that deviation because the assignment's
claimed input file did not exist and TrackFlow's production data has no revenue dimension. The
deterministic generator is `scripts/generate_trackflow_sales.py` and uses seed 42. Generated,
strongly seasonal data is easier to learn than real revenue, so these results are optimistic.

## Model decision

Random Forest was selected over XGBoost for three predeclared reasons: only 84 post-lag
training observations are available; independent bagged trees are easier to explain to Finance;
and per-tree disagreement provides the requested variability band without another modelling
assumption. Hyperparameters were fixed before the holdout was inspected, with no Phase 6.5.a tuning
budget. Tree ensembles are scale-invariant, so no meaningless scaling transform was fitted.

## Forecast protocol and features

The model trains only on 2016-01 through 2023-12 and forecasts all 24 months from the 2023-12
origin. Each tree recursively supplies its own future lag values; no observed 2024–2025 revenue,
shipment count, or average revenue per shipment enters any test feature.

Features are cyclic month, quarter, peak/trough flags, a monotonic time index, and revenue lags at
1 and 12 months. Calendar values are known in advance; both revenue lags are strictly prior-period
values. Same-month `shipments_processed` and `avg_revenue_per_shipment_eur` are excluded because
they definitionally reveal the target.

## Holdout metrics

- MSE: 4,234,779,297.39 EUR².
- RMSE: 65,075.18 EUR, or
  9.03% of mean monthly test revenue. RMSE is the
  dimensionally meaningful percentage substitute for MSE.
- PSI over predicted revenue: 11.0910
  (significant shift). Expected is the in-sample training-prediction
  distribution; actual is the strict recursive test-prediction distribution; ten quantile bins
  come from training only. This comparison spans earlier training years against later, growing test
  years, so a large value can reflect the known trend and bounded tree extrapolation rather than an
  unexpected regime change. The consolidated-only dataset cannot measure an LA/ZGZ volume-mix
  shift, so no geographic interpretation is claimed.
- Continuous-target Gini (Somers' D):
  0.5000. This is
  `(concordant - discordant) / comparable actual pairs` and measures rank ordering.
- D'Agostino–Pearson K² on 24 test residuals:
  statistic 7.7936, p-value 0.0203. This is a
  residual-structure diagnostic, not accuracy; n=24 gives it low power.

A low MSE alone cannot establish ranking quality, distribution stability, or whether residuals
retain unmodelled structure. The chart's P10–P90 range is ensemble spread, not a calibrated
confidence or prediction interval.
