# Sales Forecasting Project Instructions

These brief-like instructions complement [`sales_prediction.md`](sales_prediction.md).

## Part 1: Sales Forecasting with a Regression Model

Leadership wants to know how much the company is going to sell in the coming months, not just classify an outcome into categories. That's a regression problem.

Your tech lead has opened a ticket based on an RFI that came in from Finance: they want to know whether, with the available historical data, it's feasible to predict future sales behavior with an acceptable margin of error before committing to building a full executive dashboard around it.

> **From:** Your tech lead
> **Subject:** Ticket — Sales prediction model
>
> Finance wants to know if we can predict sales for the coming months up to a year in advance based off of the data from the historical data. Before we promise them anything, I need a model trained and evaluated honestly: no claiming a low error just because the model memorized the past. So you first you need to search what current models exist that does this well, hugging face if needed.

### Non-negotiable criteria

- You will have 10 years of historical data total. Use the first 8 years of data for training and the 2 most recent years to check the prediction — the model must not have seen those recent years during training.
- I want a visualization showing the prediction along with its variability range (not a single optimistic number).
- Justify why you chose XGBoost or Random Forest for this case — don't assume one is "better" without arguing it.
- Report the error with a metric I can explain to Finance without it sounding like a black box.

### Complementary knowledge

Random Forest trains many decision trees on different subsets of the data and averages their results — it's simpler to explain and a good starting point. XGBoost trains trees sequentially, where each one corrects the errors of the previous one — it usually predicts better but is harder to explain and needs more tuning. Choose based on what your stakeholder actually needs: explainability or maximum accuracy.

### How to Start the Project

1. From `main` in your fork, create a new branch for this project (in Codespaces or in your local environment).
2. Then add dependencies with `uv add` (for example, `scikit-learn`, `xgboost`, `pandas`, and `matplotlib`).
3. Use your company's historical sales dataset already provided: in the monorepo it is located at `data/raw/<company>_sales.csv`, and in this reference repository at `content/contexts/sales-forecasting/<company>/<company>_sales.csv`; do not generate or simulate it.
4. Read the full [`sales_prediction.md`](sales_prediction.md) before writing code: it contains each column's meaning, the date range, and the seasonality pattern the dataset already reflects.

### What You Need to Do

#### Data preparation

- [ ] Load your company's historical sales dataset from the path that matches your working environment: `data/raw/<company>_sales.csv` in your monorepo or `content/contexts/sales-forecasting/<company>/<company>_sales.csv` in this reference repository, and verify the columns match those described in your `CONTEXT-company.md`.
- [ ] Handle null or empty values before training.
- [ ] Split the dataset into training (the first 8 years) and checking/test (the 2 most recent years), so the model never sees the test years during training.
- [ ] Scale the variables that need it to avoid faulty comparisons between different magnitudes.

#### Model training

- [ ] Train a regression model using XGBoost or Random Forest (pick one and document why) with scikit-learn.
- [ ] Document, in code or in a comment, the criteria used to choose the algorithm (data size, need for explainability, time available for tuning).

#### Evaluation

- [ ] Calculate and report at least the following metrics on the test set: MSE, PSI, Gini, and K2 Score.
- [ ] Explain in your implementation's README (or in a comment) what each metric measures and why a low MSE alone isn't enough.

#### Visualization

- [ ] Generate a visualization showing the model's prediction along with the variability area of the result, compared against the real data from the 2 test years.

> **Important:** Column names, dataset format, and specific values in your implementation must match what is specified in your `CONTEXT.md`. A generic implementation that ignores your company's context will not be accepted.

#### Testing

- [ ] Add at least one unit test in `tests/pipelines/` that validates the training/test split respects the 8-year / 2-year rule and that there is no data leakage between the two sets.

### What We Will Evaluate

- [ ] The training/test split respects the 8-year / 2-year rule and does not mix data between the two sets.
- [ ] The model trained is XGBoost or Random Forest, with the choice explicitly justified.
- [ ] All four metrics (MSE, PSI, Gini, K2 Score) are calculated and reported on the test set, not the training set.
- [ ] There is a visualization showing the prediction along with its variability range, not just a point estimate.
- [ ] The dataset used is the one provided in `data/raw/<company>_sales.csv`, with no alterations that break the seasonality and growth pattern described in the company's [`sales_prediction.md`](sales_prediction.md).
- [ ] The random seed (`random_state` / `seed`) is fixed so the experiment is reproducible. But if needed to fit more of the context of the repo, we can consider increasing or adjusting the seed data to make it more suitable and robust for the project.
- [ ] The split's unit test passes correctly.

## Part 2: Evaluating a Regression Model

You already trained a regression model to predict your company's sales and tuned its hyperparameters. But a trained model is not the same as a trustworthy one: your tech lead has opened a ticket requesting a formal technical evaluation before approving its promotion to staging. No one is going to move a model to production just because "the final error looks fine."

The ticket is specific and includes three questions your report must answer without ambiguity:

1. Does the model show underfitting, overfitting, or is it reasonably well fitted?
2. How stable is its performance when you change which portion of the data you train on?
3. If there is a problem, what is the specific corrective action — not a generic one — that should be taken?

Answering "the model works fine" without evidence isn't a technical evaluation, it's an opinion. Your report must be backed by learning curves, cross-validation, and justified metrics.

### Complementary knowledge: bias, variance, and learning curves

A model with underfitting fails even on the training data: it didn't capture the pattern. A model with overfitting memorizes the training noise and fails to generalize. The most reliable way to diagnose which one is happening (or whether neither is) is a learning curve: plotting the training error and the validation error as the training set size increases.

- If both curves converge at a high error → underfitting. The typical fix is increasing model complexity or reviewing feature quality — never adding more data as the first response.
- If there is a wide, persistent gap between training (low) and validation (high) → overfitting. The typical fix is regularization, reducing complexity, or more data — never increasing complexity as the first response.
- If both curves converge at a low, close error → the model is reasonably well fitted.

There is no universal "correct" curve — what matters is the relative pattern between the two lines.

### How to Start the Project

1. Confirm that the trained model and the temporal split (8 years train / 2 years test) from your previous project are still available and reproducible.
2. Install any additional dependencies with `uv add`.
3. Read [`sales_prediction.md`](sales_prediction.md) to understand which error is more costly for your business: overestimating sales or underestimating them. If it is decided that something needs to be added for the goal and objective of the repo, then we can brainstorm further.

### What You Need to Do

#### Time-aware cross-validation

- [ ] Implement a temporal cross-validation strategy (e.g. `TimeSeriesSplit`) with at least 5 folds over the training set.
- [ ] Explicitly verify that no fold mixes or shuffles the data — chronological order must be preserved within each fold.
- [ ] Report the chosen metric as mean ± standard deviation across folds, not just a single aggregate number.

#### Learning curve

- [ ] Generate a learning curve plotting training error and validation error as the training set size grows.
- [ ] Save the resulting image to `data/eval/`.

#### Metric selection and calculation

- [ ] Calculate MAE and RMSE for training and validation.
- [ ] Justify in writing which one better reflects the business cost of your errors, based on what [`sales_prediction.md`](sales_prediction.md) indicates.

> **Important:** Field names, entity IDs, and domain-specific values in your implementation must match what is specified in [`sales_prediction.md`](sales_prediction.md), or what we decide to alter or add in the planning according to the goal of the project. A generic implementation that ignores the context will not be accepted.

#### Diagnosis and technical report

- [ ] Write a technical report (`data/eval/evaluation_report.md`) that explicitly classifies the model as well fitted, underfitting, or overfitting, backed by the learning curve and the cross-validation results.
- [ ] Propose a concrete corrective action consistent with the diagnosis — not a generic answer like "add more data" or "increase complexity" without justifying why that is the root cause.

#### Testing

- [ ] Write a unit test in `tests/pipelines/` that validates the temporal cross-validation strategy preserves the chronological order of the data within each fold (no index from a later fold appears before one from an earlier fold).

### What We Will Evaluate

- [ ] The learning curve is generated correctly and its pattern (underfitting / overfitting / good fit) is explicitly interpreted in the report.
- [ ] The temporal cross-validation does not shuffle the data and reports mean ± standard deviation.
- [ ] At least two regression metrics are calculated and compared, with a business justification for the one chosen as primary.
- [ ] The report gives an explicit diagnosis (well fitted / underfitting / overfitting) backed by evidence, not just an assertion.
- [ ] The proposed corrective action is specific and consistent with the given diagnosis — not a generic recommendation.
- [ ] The unit test on fold chronological order passes correctly.
