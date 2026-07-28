# Engagement 6.5 Sales Forecasting — Implementation Plan

**Plan status:** Proposed for owner review
**Specification:** `docs/planning/remaining_planning/spec-6.5-sales-forecasting.md`
**Owner:** Cory McDaniel
**Scope:** Engagement 6.5 only
**Delivery relationship:** This plan is independent of, and runs in parallel with, Engagement
6.1–6.4. It is not blocked by or sequenced behind the reporting-reliability work.

## 1. Authority, intent, and boundaries

The owner-approved 6.5 specification is binding. The files under
`docs/planning/remaining_planning/sales_forcasting/` are bootcamp requirements and context, not an
independent architecture authority. Where those inputs disagree with the specification, this plan
follows the specification and records the deviation rather than concealing it.

The engagement produces a reproducible **offline regression and evaluation artifact**. It does not
add model serving, an HTTP endpoint, a database or migration, Supabase access, a production
schedule, a container or Compose service, a Back Office route, or a production runtime import.
Nothing in the 6.1–6.4 scope, `services/central-api/` runtime code, `docker/`, Compose, GitHub
workflows, or `packages/` may be modified.

Implementation has exactly two phases:

1. **6.5.a — Regression model**
2. **6.5.b — Formal evaluation**

Each phase ends with a written evidence package and a hard stop for owner review and approval. Work
on 6.5.b must not start until the owner approves 6.5.a in writing.

## 2. Required reading completed for this plan

The following sources were read end to end:

- `memory-bank/projectbrief.md`, `memory-bank/techContext.md`, and `memory-bank/progress.md`
- `AGENTS.md`, `CLAUDE.md`, and the root `README.md`
- `docs/planning/remaining_planning/README.md`
- `docs/planning/remaining_planning/spec-6.5-sales-forecasting.md`
- `docs/planning/remaining_planning/sales_forcasting/sales_prediction.md`
- `docs/planning/remaining_planning/sales_forcasting/sales_forecasting_project_instructions.md`
- `docs/planning/remaining_planning/spec.md` §0.4
- `docs/briefs/06-data-pipelines-telemetry.md` and `docs/briefs/README.md`
- `.agents/rules/testing-error-handling-ci.md` and
  `.agents/rules/compliance-licensing.md`
- `docs/standards/testing.md`, `error-handling.md`, `observability.md`,
  `production-readiness.md`, and `compliance-licensing-standard.md`
- The relevant folder READMEs under `data/`, `data/raw/`, `data/process/`, `data/eval/`,
  `data/pipelines/`, `data/pipelines/business_performance/`, and `scripts/`
- The delivered generator and CSV, the existing pure-transform and pipeline-test conventions,
  `data/pyproject.toml`, `data/uv.lock`, `services/central-api/pyproject.toml`,
  `docker/central-api.Dockerfile`, and `THIRD_PARTY_LICENSES.md`

## 3. Confirmed repository baseline

- The permanent files do not yet exist at `data/raw/trackflow_sales.csv` and
  `scripts/generate_trackflow_sales.py`; the delivered copies remain in the planning-input folder.
- The delivered CSV has 120 monthly `consolidated` rows from 2016-01 through 2025-12 and the exact
  five-column schema in the specification.
- A read-only validation of the planning copy succeeded with `python3 ... --check`; it reported
  2016 revenue of 5,204,105 EUR and 2025 revenue of 8,965,817 EUR and found no specification
  violations. This is baseline evidence only and does not replace the mandatory validation after
  relocation.
- The delivered generator is standard-library-only and deterministic with seed 42.
- `data/pyproject.toml` has a `dev` optional group but no forecasting group; `data/uv.lock` contains
  none of the proposed ML/plotting packages.
- The data project packages `pipelines` and `process`, enforces strict mypy and Ruff, and currently
  has a 90% branch-coverage threshold.
- `docker/central-api.Dockerfile` copies the entire `data/` tree and installs Central API with
  `uv sync --frozen --no-dev`. Central API depends on the local data project without extras.
- Existing unrelated worktree changes are present. They must be inventoried and preserved; the
  implementation may stage only owner-approved 6.5 files.
- In this local shell, `python` is not on `PATH`; `python3` and `uv run --project data python ...`
  are available.

## 4. Ambiguities and owner decisions required

These items are not resolved silently. The recommendations below become binding only when the owner
approves this plan or records a different choice.

### 4.1 Relocated generator default conflicts with the required command

The delivered generator defaults `--output` to a CSV beside `__file__`. After relocation, the
specification's bare command:

```bash
python scripts/generate_trackflow_sales.py --check
```

would look for `scripts/trackflow_sales.csv`, not `data/raw/trackflow_sales.csv`, and fail.

**Recommendation:** preserve relocation as the first repository mutation, then run the first
mandatory check with an explicit target:

```bash
uv run --project data python scripts/generate_trackflow_sales.py \
  --output data/raw/trackflow_sales.csv --check
```

Stop immediately on a non-zero result. Only after that passes, change the generator's permanent
default to the repository's `data/raw/trackflow_sales.csv`, add CLI tests for invocation from the
repository root, and prove the no-argument `--check` command uses the permanent CSV. Use the data
project interpreter because this shell has no bare `python`; documentation may show the
specification's portable `python ...` form while the local evidence records the actual `uv run`
command.

### 4.2 Forecast protocol when lagged targets are used

The specification permits lagged revenue but does not define whether the 24-month holdout is:

- a recursive/multi-horizon forecast using only history available at the 2023-12 cutoff, or
- a rolling one-step backtest that may use an observed prior test month as a lag for the next
  prediction.

Those protocols answer different business questions and can produce materially different errors.
Using actual 2024 revenue to construct 2025 features is not training leakage, but it is unavailable
to a forecast issued at the end of 2023.

**Recommendation:** define the artifact as a strict origin-time forecast: no actual target from the
24-month test partition may enter any test feature. If lagged targets are selected, generate the
holdout recursively from training-observed and then model-predicted history. Also report the
operational horizon limitation: the ticket asks for forecasts up to one year, while the mandated
holdout contains two years. If the owner prefers rolling one-step evaluation, label it explicitly
and do not describe it as a two-year advance forecast.

### 4.3 Feature contract and resulting training row count

The specification names permitted feature families but does not select an exact feature set.
Random Forest also cannot extrapolate a continuous trend beyond the largest training value in the
same way a parametric trend model can.

**Recommendation:** freeze and document one causal feature contract before fitting: cyclic
month-of-year, quarter, peak/trough flags, monotonic time index, and a small predeclared set of
strictly prior-period lags. Record the resulting training count after lag warm-up. Do not select
features by inspecting 2024–2025 errors. If the owner prefers calendar-only features to avoid
recursive lags, record the loss of trend-carrying information as a known model limitation.

### 4.4 Estimator configuration and tuning budget

The specification recommends Random Forest but does not fix its hyperparameters or a tuning budget.

**Recommendation:** use `RandomForestRegressor` with a small, predeclared configuration, a fixed
seed, and no holdout-driven tuning in 6.5.a. Record every parameter in the artifact manifest.
Formal time-aware cross-validation belongs to 6.5.b; any tuning suggested by its diagnosis is a
specific corrective action for a later owner-approved rerun, not a reason to rewrite the accepted
6.5.a result retroactively. An XGBoost departure requires the additional written argument and
overfitting controls required by specification §2.1.

### 4.5 PSI subject

The specification permits PSI over model predictions or a named feature but does not choose one.
The assignment's desired LA/Zaragoza volume-mix interpretation is impossible because every row is
`consolidated`.

**Recommendation:** compute PSI over predicted monthly revenue, with expected bins and proportions
derived from training predictions only and actual proportions from test predictions. State whether
training predictions are in-sample or out-of-fold. Report that this measures distribution shift in
model output, not geographic mix, and that the deterministic generator contains no regime change.

### 4.6 Variability-band percentiles

The percentile bounds are not fixed.

**Recommendation:** use the 10th–90th percentiles of per-tree predictions and label the band
“Random Forest ensemble spread (P10–P90), not a calibrated prediction interval” in both chart and
report. Recursive forecasts must propagate each tree/path consistently rather than combining
future actual targets with predictions.

### 4.7 Artifact names and serialization

The specification fixes directories but not filenames, model serialization, schema versions, or
overwrite behavior.

**Recommendation:** owner-approve a versioned artifact contract before implementation, including:

- a model artifact plus a JSON manifest containing seed, package versions, feature names, split,
  estimator parameters, forecast protocol, and content hashes;
- `sales_forecast_metrics.v1.json`;
- a versioned prediction table and prediction chart;
- a versioned learning-curve image; and
- the fixed `data/eval/evaluation_report.md`.

The training command should write atomically and refuse an ambiguous partial artifact set.
Serialized Python model files must be treated as trusted local build artifacts and never loaded
from an untrusted source.

### 4.8 Image-size acceptance is not numerically defined

“Effectively zero” and “unchanged in size” have no measurement method or tolerance. Literal byte
equality is impossible to promise because the Dockerfile copies the whole `data/` directory, so the
new source, CSV, model, JSON, and images themselves enter the build context even when no ML package
is installed.

**Recommendation:** use the same clean-build command and base image for both measurements; record
uncompressed image size in bytes, compressed archive size if used, and the exact delta. Make the
hard dependency gate: none of `pandas`, `numpy`, `scipy`, `sklearn`, `matplotlib`, or `xgboost` is
installed in the image virtual environment. Report the residual source/artifact byte delta
separately. Before implementation, the owner must either define an allowed artifact-only tolerance
or approve “zero ML dependency contribution” as the intended meaning. Do not change Docker or
`.dockerignore` to force equality without a specification amendment.

### 4.9 Lockfile omitted from §7

Specification §3 requires `uv add`, and the compliance standard requires lockfiles to remain in
sync, but specification §7 does not name `data/uv.lock` among modified files.

**Recommendation:** treat `data/uv.lock` as implied dependency metadata and include only its
forecasting-extra resolution changes. Owner approval of this plan confirms that interpretation.
Otherwise dependency addition cannot proceed compliantly.

### 4.10 Attribution wording is stricter than the repository standard

Specification §3 requires every new package, version, and license to be recorded in
`THIRD_PARTY_LICENSES.md`. The current licensing standard and register enumerate non-permissive
packages individually while covering permissive dependencies through generated audits.

**Recommendation:** follow the stricter specification for this engagement: add a clearly scoped
forecasting table for every direct package and any non-permissive transitive dependency, record the
full transitive audit as review evidence, and do not weaken the existing register. Stop for owner
approval before adopting any copyleft, non-commercial, custom, or unlicensed dependency.

### 4.11 Image baseline timing

The plan must begin with relocation/check, while specification §3 also asks for an image built
before the change.

**Recommendation:** if a suitable immutable baseline image is not already recorded, build and
record it as a read-only preflight immediately before the first repository mutation. Relocation
remains the first implementation change. If the owner interprets “starts by relocating” as
forbidding even this preflight, record the baseline immediately after relocation/check and label
the comparison as isolating dependency/artifact additions rather than the full phase.

## 5. Phase 6.5.a — Regression model

### 5.1 Entry conditions

- The owner has approved this plan and resolved or accepted the recommendations in §4.
- The current branch and complete worktree status are recorded without staging, discarding, or
  rewriting unrelated changes.
- The delivered CSV and generator hashes are recorded so relocation can be proven byte-preserving.
- If approved under §4.11, the pre-change Central API image size and image ID are recorded using a
  reproducible build command.

### 5.2 Implementation sequence

#### Step 1 — Relocate first, validate immediately, and stop on failure

1. Relocate, without regenerating or editing:
   - `sales_forcasting/trackflow_sales.csv` → `data/raw/trackflow_sales.csv`
   - `sales_forcasting/generate_trackflow_sales.py` →
     `scripts/generate_trackflow_sales.py`
2. Verify source/destination hashes prove byte-preserving relocation.
3. Run the relocated generator against the relocated CSV with the explicit `--output` command in
   §4.1.
4. Capture stdout, exit status, row count, date range, schema, seed, growth/seasonality summary,
   and internal-consistency result.
5. **If validation fails, stop Phase 6.5.a immediately.** Do not regenerate the CSV, add
   dependencies, or begin model work. Present the failure and hashes to the owner.

This is the first implementation gate and cannot be bypassed by the successful planning-copy check.

#### Step 2 — Repair and test the permanent generator contract

1. Change the relocated generator's default path so root invocation validates or regenerates
   `data/raw/trackflow_sales.csv`, independent of the caller's current working directory.
2. Preserve standard-library-only operation, seed 42, byte-identical regeneration, and the
   existing provenance explanation.
3. Add tests that cover:
   - bare `--check` resolving the permanent CSV;
   - successful validation of the delivered file;
   - malformed schema, missing/null fields, missing/duplicate months, non-consolidated rows,
     non-positive values, and numeric inconsistency failing loudly; and
   - regeneration to a temporary file matching the committed CSV byte-for-byte.
4. Run the specification's bare command through the data-project interpreter and attach the
   passing evidence.

#### Step 3 — Add isolated forecasting dependencies and licensing evidence

1. Confirm the Random Forest decision (or document the owner-approved XGBoost departure) before
   changing dependencies.
2. Use `uv add --project data --optional forecasting ...`; never use `pip install`.
3. Add only packages actually used by the offline implementation: scikit-learn, matplotlib, and
   SciPy are expected; add pandas only if the accepted implementation actually uses it and records
   why the standard library plus NumPy/scikit-learn are insufficient. Do not add XGBoost when
   Random Forest is selected.
4. Keep the normal data-project dependencies and Central API's path dependency free of the
   forecasting extra. Update `data/uv.lock` only as approved in §4.9.
5. Verify direct and transitive licenses and vulnerabilities. Update
   `THIRD_PARTY_LICENSES.md` under the §4.10 interpretation.
6. Prove that `uv sync --frozen --no-dev` for Central API does not install the optional group.

#### Step 4 — Implement pure data, split, feature, and metric contracts

Create pure, typed, deterministic logic under `data/process/sales_forecasting/`, following the
existing `data/process/business_performance/` pattern:

1. Validate the exact schema, parse `month` strictly, require only `consolidated` rows, sort
   chronologically, reject null/empty/non-finite/non-positive values, and require the complete
   2016-01 to 2025-12 monthly sequence.
2. Split by explicit dates:
   - train: 2016-01 through 2023-12 (96 source rows);
   - test: 2024-01 through 2025-12 (24 source rows).
3. Assert no row/index overlap and ensure no fit, bin, scaler, feature selection, or parameter
   selection sees test data.
4. Build only the owner-approved causal feature contract from §4.2–§4.3. Exclude same-month
   `shipments_processed`, `avg_revenue_per_shipment_eur`, and target-derived values. Use only
   trailing windows. State the final post-lag training count.
5. Do not scale tree features merely to satisfy the assignment checklist. Document why tree
   ensembles are scale-invariant. If any scale-sensitive component is later approved, fit its
   scaler on training folds only.
6. Implement and test the binding metrics:
   - test MSE in EUR² plus RMSE as a percentage of mean test revenue;
   - PSI using training-derived 10-quantile bins, declared subject, and a documented epsilon;
   - continuous-target Gini as Somers' D with tie/comparable-pair behavior documented; and
   - D'Agostino–Pearson K² on the 24 test residuals, statistic and p-value.
7. Keep the pure layer free of I/O, environment reads, model serving, and production-runtime
   imports.

#### Step 5 — Train reproducibly and generate Phase 6.5.a artifacts

Implement `scripts/train_sales_forecast.py` as a thin offline entry point:

1. Load the fixed permanent CSV and call the pure validation/split/feature functions.
2. Train the approved estimator only on the training partition with fixed seeds and the recorded
   configuration; never use test performance to select it.
3. Produce predictions under the approved forecast protocol.
4. Compute all four binding metrics only on the test partition.
5. Derive the approved ensemble-spread band and plot actual, predicted, and band for all 24 test
   months with units, dates, legend, accessible labels, and the non-calibration warning.
6. Write the owner-approved, versioned model, manifest, predictions, metrics JSON, and chart under
   `data/eval/` atomically.
7. Record package versions, seed, input hash, feature list, split dates/counts, estimator
   parameters, forecast protocol, metric definitions, and artifact hashes.
8. Run twice from a clean artifact directory and prove the metrics and deterministic artifacts
   reproduce. If a binary/image contains nondeterministic metadata, compare semantic content and
   record the limitation rather than claiming byte identity.

#### Step 6 — Add focused tests and dependency-boundary proof

Add `tests/pipelines/test_sales_forecasting.py` with unit-level coverage for at least:

- exact 8-year/2-year split boundaries, counts, and no overlap;
- missing/out-of-order/duplicate/null/invalid input rejection;
- feature provenance and a hard assertion that no feature uses the same month's target,
  shipments, or average revenue per shipment;
- strict prior-period behavior for every lag/rolling feature and the approved test forecast
  protocol;
- fixed-seed reproducibility;
- hand-calculated metric fixtures, including PSI empty-bin epsilon, Somers' D ties, and K²
  output/short-input failure behavior;
- generator path/validation/regeneration behavior; and
- artifact schema/version validation.

Add an import-boundary test that statically traces repository-local imports reachable from
`central_api.main`, `pipelines.business_performance.worker`, and
`scripts.maintenance_worker`, failing if they reach `process.sales_forecasting`, the training
script, or any ML/plotting package. Complement it with inspection of the built production image.
The test must not require production credentials or import modules in a way that opens a database.

#### Step 7 — Verify image and quality gates

1. Build `docker/central-api.Dockerfile` after the phase with the same command, context, base image,
   and measurement method as the baseline.
2. Record image ID, exact size, baseline, total delta, and the artifact-only interpretation
   approved in §4.8.
3. Inside the image virtual environment, prove forecasting modules have no production import path
   and ML/plotting packages are absent.
4. Run:

```bash
uv run --project data --extra forecasting --extra dev \
  ruff check data/process scripts/generate_trackflow_sales.py \
  scripts/train_sales_forecast.py tests/pipelines/test_sales_forecasting.py
uv run --project data --extra forecasting --extra dev \
  mypy --config-file data/pyproject.toml data/process \
  scripts/generate_trackflow_sales.py scripts/train_sales_forecast.py
uv run --project data --extra forecasting --extra dev \
  pytest -c data/pyproject.toml tests/pipelines/test_sales_forecasting.py
uv run --project data --extra forecasting --extra dev \
  pytest -c data/pyproject.toml tests/pipelines \
  --cov=pipelines --cov=process --cov-config=data/pyproject.toml --cov-report=term-missing
uv build --project data
```

Adjust command syntax only if verified against the installed `uv` version, and record any
adjustment. Preserve or improve the existing 90% branch-coverage gate. Run Central API's applicable
lint, type-check, build, and tests if dependency/import-boundary metadata causes it to be touched by
the verification path, without modifying Central API code.

#### Step 8 — Update tracking documentation minimally

Update only the tracking files authorized by specification §7:

- root `README.md` roadmap and “What's Been Built”;
- `docs/briefs/06-data-pipelines-telemetry.md` status only, without rewriting stakeholder scope;
- `docs/briefs/README.md`;
- `CLAUDE.md` “Where New Engagement Code Goes”;
- `memory-bank/progress.md`; and
- `data/README.md` as the deliverable-folder README.

State that 6.5.a is delivered/pending review while 6.5.b remains unstarted. Preserve the explicit
parallel relationship with 6.1–6.4 and do not claim model serving or production readiness.

### 5.3 Phase 6.5.a acceptance and evidence package

Present:

- relocation hashes and the mandatory relocated `--check` output;
- generator CLI/regeneration test evidence;
- exact split dates and source/post-feature row counts;
- feature-provenance and leakage-test evidence;
- estimator rationale, fixed configuration, tuning budget, and forecast protocol;
- versioned manifest, model, metrics JSON, prediction table, and prediction chart;
- MSE/RMSE%, PSI, Somers' D, and K² with definitions and limitations;
- repeat-run reproducibility evidence;
- dependency and license audit;
- import-graph test and production-image package inspection;
- before/after image measurements under the owner-approved tolerance;
- Ruff, mypy, targeted/full pytest with coverage, and build results;
- tracking-doc diff and a protected/unrelated-file audit; and
- proposed commit message: `Engagement 6.5.a: add offline sales regression model`.

**STOP FOR OWNER REVIEW AND WRITTEN APPROVAL.** Do not stage unrelated files, commit the phase, or
begin 6.5.b until the owner directs the exact review/commit sequence. After approval, stage only
the accepted phase files and use a phase-naming commit message.

## 6. Phase 6.5.b — Formal evaluation

### 6.1 Entry conditions

- Written owner approval of the complete 6.5.a evidence package.
- The accepted 6.5.a commit/artifact hashes are recorded and reproducible.
- No unresolved 6.5.a correction is being hidden inside 6.5.b.

### 6.2 Implementation sequence

#### Step 1 — Implement chronological cross-validation

1. Add a pure time-aware evaluation function using `TimeSeriesSplit` or an equivalent with at
   least five folds over the **training partition only**.
2. Apply feature construction independently within each fold so validation data cannot influence
   lags, rolling values, bins, scaling, feature selection, or estimator fitting.
3. Assert chronological ordering within every fold, train-before-validation ordering, no overlap,
   no shuffle, and no test-partition index in any fold.
4. Record each fold's raw and post-feature train/validation sizes and date boundaries.
5. Compute per-fold MAE and RMSE and report each selected metric as mean ± standard deviation.
   Explain the small validation partitions created from 96 source training rows.

#### Step 2 — Generate and interpret the learning curve

1. Use chronological training prefixes rather than shuffled subsamples.
2. For every prefix, fit feature construction and the estimator without future-fold information.
3. Calculate comparable training and validation MAE/RMSE and save the versioned learning-curve
   image under `data/eval/`.
4. Interpret the relative gap and convergence pattern, not an invented universal error threshold.
5. Keep the 2024–2025 holdout untouched by cross-validation and learning-curve diagnosis.

#### Step 3 — Write the formal evaluation report

Create `data/eval/evaluation_report.md` containing:

1. Dataset provenance and the explicit owner-approved deviation: the CSV is generated, not
   provided or observed, with links to the generator, seed, and data/manifest hashes.
2. Algorithm choice against data size, explainability, and tuning budget.
3. Exact causal features, advance-knowledge justification, split/protocol, source and post-lag
   row counts, seeds, and package versions.
4. Test MSE, RMSE%, PSI, Somers' D, and K² with binding formulas, interpretations, and limitations.
5. The explicit statement that LA/Zaragoza PSI is not computable from consolidated-only data.
6. Training/validation MAE and RMSE, fold results, mean ± standard deviation, and the argument for
   the primary business metric. Derive the cost position from peak-season staffing risk rather
   than asserting it without evidence.
7. The learning curve and a single explicit, evidence-backed classification: well fitted,
   underfitting, or overfitting.
8. One specific corrective action tied to the observed root cause. Do not use generic “add data”
   or “increase complexity” language.
9. Unambiguous answers to the ticket's three questions: fit diagnosis, stability across temporal
   partitions, and corrective action.
10. The complete honesty section:
    - generated rather than observed data;
    - deterministic seasonality is easier than real revenue and makes errors optimistic;
    - stable PSI reflects a generator without regime change, not demonstrated model robustness;
    - only 96 source training months bound every conclusion;
    - ensemble spread is not a calibrated predictive interval; and
    - the offline artifact is not approved for serving or operational decisions.

#### Step 4 — Extend tests and reproduce the evaluation

Add tests proving:

- chronological order within and across every fold;
- no fold shuffles, overlaps, or reaches the 2024–2025 test set;
- fold-local feature construction has no future leakage;
- at least five folds and reported fold sizes;
- mean and population/sample standard-deviation convention is explicit and correct;
- learning-curve prefixes grow chronologically;
- MAE/RMSE calculations and report/artifact schemas are correct; and
- the full evaluation rerun reproduces the reported numeric results.

Run the same Ruff, strict mypy, full pipeline pytest/coverage, and data build gates as 6.5.a. Rerun
the import-boundary and production-image package-absence checks. Compare the 6.5.b image to the
accepted 6.5.a image under the same measurement rule, since evaluation images/report content are
also copied by the current Dockerfile.

#### Step 5 — Complete tracking documentation

Update the same authorized tracking files to mark 6.5 complete only if every 6.5.b acceptance
criterion passes. Keep 6.1–6.4 status independent and factual. Document the offline-only result,
not a deployed forecasting capability.

### 6.3 Phase 6.5.b acceptance and evidence package

Present:

- fold boundaries, sizes, order tests, and mean ± standard deviation results;
- learning-curve image and relative-pattern interpretation;
- training/validation MAE and RMSE with the business metric rationale;
- the explicit fit diagnosis and root-cause-specific corrective action;
- the complete evaluation report and honesty section;
- reproducibility and artifact hashes;
- unchanged import isolation and absence of ML packages from the production image;
- image-size comparison under the approved interpretation;
- Ruff, mypy, full pytest/coverage, and build results;
- tracking-doc and protected/unrelated-file audit; and
- proposed commit message: `Engagement 6.5.b: add formal sales forecast evaluation`.

**STOP FOR OWNER REVIEW AND WRITTEN APPROVAL.** Do not merge, deploy, add serving, or begin a later
engagement as an implied continuation.

## 7. Final file-scope guard

Expected new files are limited to:

- `data/raw/trackflow_sales.csv`
- `scripts/generate_trackflow_sales.py`
- `scripts/train_sales_forecast.py`
- `data/process/sales_forecasting/`
- `tests/pipelines/test_sales_forecasting.py`
- the owner-approved versioned artifacts under `data/eval/`

Expected modified files are limited to:

- `data/pyproject.toml`
- `data/uv.lock`, subject to the explicit owner decision in §4.9
- `THIRD_PARTY_LICENSES.md`
- `README.md`
- `docs/briefs/06-data-pipelines-telemetry.md`
- `docs/briefs/README.md`
- `CLAUDE.md`
- `memory-bank/progress.md`
- `data/README.md`

The planning copies of the CSV and generator disappear only through their byte-preserving
relocation. No other planning input is rewritten. Anything outside this list requires a spec
clarification and owner approval before editing.
