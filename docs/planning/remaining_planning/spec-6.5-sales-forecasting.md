# Specification — Engagement 6.5 Sales Forecasting

**Status:** approved for implementation planning.
**Scope:** Engagement 6.5 only — offline revenue regression and its formal evaluation.
**Relationship to `spec.md`:** parallel and independent. 6.5 shares no code, no schema, no
container, and no production surface with Phases 6.1–6.4 and **must not be sequenced behind them**.
It is designed to run inside the enforced waiting periods of that work (the seven-day observation
window in 6.3, the seven-day clean run in 6.4, and the three measurement studies in 6.4).
**Owner:** Cory McDaniel. Each phase ends in an owner review-and-approval pause.

---

## 0. How to use this document

### 0.1 Required reading before planning

1. `docs/planning/remaining_planning/sales_forcasting/sales_prediction.md` — the company context:
   columns, date range, growth and seasonality patterns, KPI meanings, business constraints.
2. `docs/planning/remaining_planning/sales_forcasting/sales_forecasting_project_instructions.md` —
   the two-part assignment and its evaluation criteria.
3. `memory-bank/projectbrief.md` — stakeholders and the ~9M EUR annual revenue profile.
4. `AGENTS.md`, then `CLAUDE.md`.
5. `docs/standards/testing.md`, `error-handling.md`, `compliance-licensing-standard.md`.
6. `docs/planning/remaining_planning/spec.md` §0.4 — the standing constraints that still apply
   (preserve unrelated worktree changes; update tracking docs; stop for review after each phase).

### 0.2 Evidence classification

| Tag | Meaning |
|---|---|
| **[RF]** | Confirmed repository fact |
| **[BC]** | Bootcamp constraint — a graded requirement of the assignment |
| **[REQ]** | Requirement of this specification |
| **[REC]** | Recommendation with a stated rationale; the implementer may depart with a written argument |
| **[OD]** | Owner decision, already made |

### 0.3 Non-goals

This engagement produces an **offline analysis artifact**. It must not introduce:

- Any HTTP endpoint, serving path, or inference API.
- Any database table, migration, or Supabase access of any kind.
- Any container, Compose service, deployment change, or scheduled retraining.
- Any Back Office UI surface.
- Any change to Phases 6.1–6.4, to `packages/shared/`, to `packages/trackflow_auth`, or to any
  production runtime module.
- Any machine-learning dependency inside the Central API production image (see §3).

Model serving, if it is ever wanted, is a separate engagement with its own approval.

---

## 1. Dataset and provenance

### 1.1 Origin **[OD-10]**

`sales_prediction.md` states the dataset is "already included" at `data/raw/trackflow_sales.csv` and
instructs that it not be generated or simulated. **That file does not exist in this repository**
**[RF]**, and no production source can supply it: the operational database holds roughly two weeks
of synthetic inventory movements, carries no revenue dimension, and has effectively no history —
only 8 of 195,638 `stock_entries` rows predate 2026-07-13.

Generation was therefore approved as an explicit, documented deviation. **[REQ]** The deviation must
be stated plainly in `data/eval/evaluation_report.md` and in the pull request description. It must
not be quietly presented as provided data.

### 1.2 Delivered artifacts

Both currently live in `docs/planning/remaining_planning/sales_forcasting/` and are **relocated by
the implementer** to their permanent homes:

| Planning location | Permanent home | Contents |
|---|---|---|
| `sales_forcasting/trackflow_sales.csv` | `data/raw/trackflow_sales.csv` | 120 monthly `consolidated` rows, 2016-01 through 2025-12 |
| `sales_forcasting/generate_trackflow_sales.py` | `scripts/generate_trackflow_sales.py` | Standard-library-only, deterministic generator and validator |

### 1.3 Verified properties of the delivered dataset **[RF]**

Confirmed by running the generator's own `--report` and `--check` modes:

| Property | Value |
|---|---|
| Rows | 120, all `market = "consolidated"`, no gaps 2016-01 → 2025-12 |
| Columns | `month`, `revenue_eur`, `shipments_processed`, `avg_revenue_per_shipment_eur`, `market` |
| Seed | `random.Random(42)`, standard library — regeneration is byte-identical |
| 2016 revenue | 5,204,105 EUR |
| 2025 revenue | 8,965,817 EUR — matches the ~9M EUR company profile |
| Realized annual growth | alternating high/low, +2.0% to +10.5%, always positive |
| February | 0.855–0.899 of the year's trend monthly average (−10% to −15% band) |
| November / December | 1.256–1.346 of the trend monthly average (+25% to +35% band) |
| Internal consistency | `revenue_eur / shipments_processed` equals `avg_revenue_per_shipment_eur` to 2 dp on every row |

**Seasonality reference, stated explicitly:** the percentages are expressed relative to the **year's
trend monthly average** (annual trend ÷ 12), the natural reading of "relative to the average".
Because the November/December uplift exceeds the February drop, the *realized* annual mean sits
above the trend mean (2025: 747,151 vs 721,556 EUR), so a peak month measured against the realized
mean reads a few points lower. The generator's `--report` prints both so no reader has to guess.

**[REQ]** The implementer re-runs `python scripts/generate_trackflow_sales.py --check` against the
committed CSV as a first step and stops if validation fails.

---

## 2. Model and split decisions

### 2.1 Algorithm — Random Forest **[REC]**

The assignment requires XGBoost or Random Forest with an explicit argument, and forbids assuming one
is better **[BC]**. The argument here favours **Random Forest**, on three grounds:

1. **Data size.** 120 total rows, 96 in training. Gradient boosting builds sequential
   error-correcting trees and needs meaningful hyperparameter tuning and a validation budget to
   avoid memorising noise; at 96 observations there is no budget to spend. Bagged averaging is the
   more robust estimator at this scale.
2. **Explainability is the stated stakeholder need.** The requesting stakeholder is Finance via
   Thomas Harry (CEO), and the ticket asks for an error metric explainable "without it sounding like
   a black box". Averaged independent trees and their feature importances survive that conversation;
   a boosted ensemble's staged corrections do not.
3. **Free prediction intervals.** The per-tree prediction distribution supplies the required
   variability band (§2.5) directly, with no additional modelling assumption.

The implementer may choose XGBoost instead, but must then state the tuning budget, the
overfitting-control strategy at n=96, and how the variability band is derived. The choice and its
criteria — data size, explainability need, tuning time available — go in code comments and in the
report **[BC]**.

### 2.2 Temporal split **[BC]**

- **Train:** 2016-01 through 2023-12 — first 8 years, 96 rows.
- **Test:** 2024-01 through 2025-12 — most recent 2 years, 24 rows.
- The model must never see the test years during training, including through scaler fitting,
  feature engineering, or hyperparameter selection.
- `random_state` / `seed` fixed throughout for reproducibility **[BC]**.

### 2.3 Feature engineering and the leakage trap **[REQ]**

This is the single largest correctness risk in the assignment and must be handled explicitly.

`shipments_processed` and `avg_revenue_per_shipment_eur` are **contemporaneous with the target**.
Revenue is definitionally `shipments × average revenue per shipment`, so using either as a
same-month feature is target leakage: it hands the model the answer, and it is operationally
impossible — December's shipment count is not known before December.

Requirements:

1. Same-month `shipments_processed` and `avg_revenue_per_shipment_eur` are **excluded** as features.
2. Permitted features are causal only: calendar features (month-of-year, ideally cyclically encoded;
   quarter; a peak/trough indicator), a monotonic time index or year index, and **lagged** values
   (for example `revenue_eur` at t−1 and t−12, or lagged shipment counts) computed strictly from
   prior periods.
3. Any rolling statistic uses a trailing window only and is computed within the training partition
   before being applied forward.
4. **[REQ]** A unit test asserts that no feature column is derived from the same month's target or
   from either contemporaneous companion column.
5. The report states which features were used and why each is knowable in advance.

Note the consequence of lag features: rows lacking a full lag history at the series start are
dropped from training. State the resulting training row count explicitly.

### 2.4 Missing values and scaling **[BC]**

- The delivered dataset has no nulls or missing months, verified by the generator. The null-handling
  step is still implemented and exercised — as an explicit validation that fails loudly on a
  malformed input file, not as a silent imputation.
- **Scaling:** tree ensembles are scale-invariant, so standardising the inputs changes nothing for
  Random Forest or XGBoost. **[REQ]** Do not perform a meaningless transform to satisfy a checklist
  item. Instead, state in code and in the report *why* scaling is a no-op for the chosen estimator,
  and apply it only if a scale-sensitive component (a linear baseline, a distance-based method) is
  introduced. If a scaler is fitted at all, it is fitted on training data only.

### 2.5 Prediction with a variability band **[BC]**

A single point estimate is explicitly rejected by the ticket. Produce a chart over the 24 test
months showing actual revenue, predicted revenue, and a variability band.

**[REC]** Derive the band from the spread of per-estimator predictions in the Random Forest — for
each test month, take a percentile interval (for example 10th–90th) across the trees. This is
honest about what it represents: the ensemble's internal disagreement, **not** a calibrated
predictive interval. **[REQ]** The report must say which of the two it is; presenting ensemble
spread as a calibrated confidence interval is a misstatement.

---

## 3. Dependency isolation — a hard requirement

**[RF]** `docker/central-api.Dockerfile` performs `COPY data data` and then resolves the runtime
virtual environment with `uv sync --frozen --no-dev` from `services/central-api`. The `data/`
package therefore ships inside the Central API production image, and that single image is pulled by
Identity, Central API, `operations-feed`, the reporting worker, and `maintenance-worker` — against a
per-deployment pull already measured in the multiple-gigabyte range.

Adding scikit-learn, XGBoost, pandas, matplotlib, and SciPy to the runtime dependency set would
inflate every one of those pulls by several hundred megabytes of code production never executes, on
a 2 vCPU / 8 GB host whose declared limits are already over-committed.

**[REQ]**

1. Forecasting dependencies are declared in an **optional dependency group** that `uv sync --frozen
   --no-dev` does not install — for example `[project.optional-dependencies] forecasting = [...]` in
   `data/pyproject.toml`, installed locally with an explicit extra. Add them with `uv add`, never
   `pip install` **[BC]**.
2. **No production module may import the forecasting module.** Add a test asserting that the import
   graph reachable from `central_api.main`, `pipelines.business_performance.worker`, and
   `scripts.maintenance_worker` does not reach any forecasting module or third-party ML package.
3. **Image-size verification is an acceptance gate:** build `docker/central-api.Dockerfile` before
   and after the change and record both sizes. The delta attributable to forecasting dependencies
   must be effectively zero. Confirm the ML packages are absent from the built image's virtual
   environment.
4. New dependencies trigger `.agents/rules/compliance-licensing.md` and
   `docs/standards/compliance-licensing-standard.md`: record each package, version, and license in
   `THIRD_PARTY_LICENSES.md`.

---

## 4. Metric definitions

The assignment names MSE, PSI, Gini, and K2 for Part 1 **[BC]**. Three of those are drawn from
classification and credit-scoring practice and have no single canonical meaning for a regression
target. Leaving them undefined produces a hand-wavy deliverable — precisely what the ticket's
"no black box" framing is trying to prevent. The definitions below are binding; departures must be
argued in the report.

| Metric | Binding definition | Interpretation to report |
|---|---|---|
| **MSE** | Mean squared error on the **test set**, reported in EUR². | Also report **√MSE (RMSE) as a percentage of mean monthly test revenue**. `sales_prediction.md` asks for MSE "as a percentage of average monthly revenue", which is dimensionally impossible for a squared quantity; RMSE is the interpretable equivalent and the substitution must be stated. |
| **PSI** | Population Stability Index, `Σ (aᵢ − eᵢ) · ln(aᵢ / eᵢ)` over bins. Declare the distribution compared (the model's predicted values, or a named feature), with **expected** = training distribution and **actual** = test distribution, **10 quantile bins derived from training only**, and a small-count epsilon to avoid division by zero. | Conventional bands: < 0.10 stable, 0.10–0.25 moderate shift, > 0.25 significant shift. **Honest limitation [REQ]:** `sales_prediction.md` frames PSI as detecting a Los Angeles / Zaragoza volume-mix shift, but the dataset contains only `consolidated` rows and no market breakdown, so that specific interpretation **is not computable** from the provided columns. Say so; do not manufacture a market split to make the metric appear meaningful. |
| **Gini** | For a continuous target, `2·AUC − 1` does not apply. Use **Somers' D**: `(concordant − discordant) / comparable pairs` over (actual, predicted) pairs on the test set. State the formula used. | Measures **rank ordering** — whether the model reliably separates a low month from a high month. This maps directly to the stated stakeholder need: distinguishing a normal February from an atypical drop that warrants investigation. |
| **K2 Score** | D'Agostino–Pearson K² normality test (`scipy.stats.normaltest`) applied to **test-set residuals**. Report the statistic and the p-value. | A **residual-structure diagnostic, not an accuracy metric**. Non-normal residuals suggest unmodelled structure (for example an uncaptured seasonal term). With 24 test residuals the test has low power — state that explicitly rather than over-reading the p-value. |

All four are computed on the **test set, never the training set** **[BC]**. The report explains what
each measures and why a low MSE alone is insufficient **[BC]**.

Part 2 additionally requires **MAE** and **RMSE** for training and validation, with a written
argument for which better reflects business cost **[BC]**. `sales_prediction.md` does not state
which direction of error is more costly, so the implementer must **derive and state a position** from
the business context rather than assert one. **[REC]** RMSE as primary, because it penalises large
errors disproportionately and TrackFlow's costly mistakes cluster in the November–December peak,
where a large miss means mis-staffed warehouses in the highest-volume weeks of the year. Argue it;
do not simply copy this sentence.

---

## 5. Phase 6.5.a — Regression model

### 5.1 Deliverables

1. Dataset and generator relocated per §1.2; `--check` validation passing.
2. Pure, testable logic in **`data/process/sales_forecasting/`**, mirroring the existing
   `data/process/business_performance/` pattern: temporal split, feature construction, and the four
   metric implementations as pure functions.
3. Training entry point at **`scripts/train_sales_forecast.py`** **[BC]**, loading
   `data/raw/trackflow_sales.csv`.
4. Trained model and artifacts written to `data/eval/`, with the fixed seed recorded alongside.
5. All four metrics computed on the test set and written to a versioned metrics JSON in `data/eval/`.
6. Prediction-versus-actual chart with the variability band over the 24 test months, saved to
   `data/eval/`.
7. `tests/pipelines/test_sales_forecasting.py` **[BC]** covering, at minimum: the 8-year/2-year split
   boundary; absence of any row overlap between train and test; and the §2.3 leakage assertion.

### 5.2 Acceptance

1. The split respects the 8-year / 2-year rule with no data mixing, proven by test **[BC]**.
2. The algorithm choice is justified in writing against data size, explainability need, and tuning
   budget **[BC]**.
3. MSE, PSI, Gini, and K2 are computed on the test set under the §4 definitions, each accompanied by
   its interpretation and stated limitations **[BC]**.
4. The visualization shows prediction plus variability range against the two real test years, and
   labels the band as ensemble spread rather than a calibrated interval **[BC]**.
5. The dataset is the delivered one, with the seasonality and growth pattern intact **[BC]**.
6. Seeds are fixed; a rerun reproduces the reported metrics **[BC]**.
7. No leakage: no feature derives from the same month's target or its contemporaneous companions.
8. §3 dependency isolation verified, including the image-size measurement.
9. Unit tests pass via `python -m pytest tests/pipelines/test_sales_forecasting.py`.

**Stop for owner review.**

---

## 6. Phase 6.5.b — Formal evaluation

### 6.1 Time-aware cross-validation **[BC]**

- `TimeSeriesSplit` (or equivalent) with **at least 5 folds over the training set only**.
- Explicitly verify no fold shuffles or mixes data; chronological order is preserved within and
  across folds.
- Report the chosen metric as **mean ± standard deviation across folds**, not a single aggregate.
- Note honestly that with 96 training rows, 5 folds leave small validation partitions; report fold
  sizes so the variance figures can be read in context.

### 6.2 Learning curve **[BC]**

- Plot training error and validation error as the training set size grows.
- Save the image to `data/eval/`.
- Interpret the **relative pattern** between the two curves, not an absolute shape.

### 6.3 Diagnosis and report **[BC]**

`data/eval/evaluation_report.md` must contain:

1. An explicit classification: **well fitted, underfitting, or overfitting**, backed by the learning
   curve and the cross-validation spread — an assertion without evidence is not a diagnosis.
2. MAE and RMSE for training and validation, with the §4 business justification for the primary
   metric.
3. A **specific** corrective action consistent with the diagnosis, naming the suspected root cause.
   Generic advice ("add more data", "increase complexity") is explicitly rejected by the
   assignment **[BC]**. At n=96 with strong deterministic seasonality, the plausible findings are
   narrow — say which one the evidence supports and what you would change.
4. **A mandatory honesty section [REQ]** covering:
   - The dataset is generated, not observed, with a link to the generator and its seed.
   - A deterministic generator produces a more learnable pattern than real revenue, so reported
     errors are optimistic relative to production behaviour.
   - PSI will show little to no drift because the generator contains no regime change; a stable PSI
     here is evidence about the generator, not about model robustness.
   - The training set is 96 monthly observations, which bounds what any conclusion can support.
5. Answers to the ticket's three questions without ambiguity: is the model underfitting, overfitting,
   or well fitted; how stable is performance across training partitions; and what is the specific
   corrective action **[BC]**.

### 6.4 Testing **[BC]**

A unit test in `tests/pipelines/` asserting the temporal cross-validation preserves chronological
order within each fold — no index from a later fold appears before one from an earlier fold.

### 6.5 Acceptance

1. Learning curve generated, saved, and its pattern explicitly interpreted **[BC]**.
2. Cross-validation does not shuffle and reports mean ± standard deviation **[BC]**.
3. At least two regression metrics compared, with a business justification for the primary **[BC]**.
4. An explicit, evidence-backed diagnosis **[BC]**.
5. A specific corrective action consistent with that diagnosis **[BC]**.
6. The fold-order test passes **[BC]**.
7. The honesty section in §6.3.4 is present and complete.

**Stop for owner review.**

---

## 7. Files in scope

**New:** `data/raw/trackflow_sales.csv`; `scripts/generate_trackflow_sales.py`;
`scripts/train_sales_forecast.py`; `data/process/sales_forecasting/`;
`tests/pipelines/test_sales_forecasting.py`; `data/eval/` artifacts including
`evaluation_report.md`, the learning curve, the prediction chart, and the metrics JSON.

**Modified:** `data/pyproject.toml` (optional dependency group only); `THIRD_PARTY_LICENSES.md`;
and, per `AGENTS.md` §3, `README.md`, `docs/briefs/06-data-pipelines-telemetry.md`,
`docs/briefs/README.md`, `CLAUDE.md`, `memory-bank/progress.md`, and `data/README.md`.

**Must not be modified:** anything in scope for Phases 6.1–6.4; `services/central-api/` runtime code;
`docker/`; `compose.yaml`; `compose.coolify.yaml`; `.github/workflows/`; `packages/`.

---

## 8. Review gates

Each phase ends here. Do not begin the next phase before written owner approval.

1. Ruff, mypy, and pytest pass for every touched package.
2. The phase's acceptance criteria are met, with evidence attached — metrics output, charts, test
   results, and the image-size measurement.
3. §3 dependency isolation verified; the Central API image is unchanged in size.
4. Engagement-tracking documentation updated per `AGENTS.md` §3.
5. No protected path modified outside scope; no unrelated worktree change disturbed; nothing in
   Phases 6.1–6.4 touched.
6. Commit message names the engagement and the phase.
7. **Stop and request review.**
