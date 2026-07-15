# Milestone 6 — Business Performance Data Pipeline


# Part 1 of 3 — Designing a Business Performance Data Pipeline

## Milestone 6 — Designing a Business Performance Data Pipeline (1/3)

Over the past weeks you captured telemetry events, stored them in `telemetry_events`, and built a technical report — event volume, error rates, latency — for your own engineering team. That system stays exactly as it is. You are not touching `telemetry_events`, `services/telemetry/analysis.py`, or the `GET /telemetry/report` endpoint in this milestone.

Today your tech lead is asking for something different: a new data pipeline, designed from scratch, whose only job is to turn that same telemetry into data that describes how the business is performing — the kind of numbers a department head or the CEO would read, not the kind an engineer uses to debug a service.

> **Technical Brief — Business Performance Data Pipeline (Design Phase)**
>
> Before writing a single line of orchestration code, I need you to document the design of a new data pipeline. This one isn’t for us — it’s for the business side, the leadership team that’s been asking for a real report instead of a PDF someone assembles by hand every week.
>
> This is a new pipeline, built on top of the telemetry you already have. Your existing `telemetry_events` table, your technical report, and the `GET /telemetry/report` endpoint don’t change — they keep serving engineering exactly as before. What you’re building now reads from the same source but produces a different kind of output: numbers a non-technical stakeholder can act on.
>
> Deliverable: a design document in Markdown, committed to the monorepo. No orchestration code yet — design first, implementation next.

---

## What makes a data pipeline robust?

A data pipeline is not simply a script that moves data from one place to another. A production pipeline has well-defined stages, handles failures predictably, and can be audited. The three key attributes that separate a robust pipeline from one that “just works” are:

- **Idempotency:** running the pipeline twice on the same data produces the same result — no duplicates, no corruption.
- **Observability:** every run leaves enough traces to know what happened, when, and why.
- **Recoverability:** when the pipeline fails mid-way, the next run knows exactly where to resume.

These three attributes are what your design document must demonstrate you have thought through deeply.

---

## Build this pipeline around a real business need

A data pipeline is not infrastructure for its own sake — even less so this one. Its only reason to exist is a business question that your companies context already scopes for you, but that nobody is answering reliably today.

Before you design extraction, transformation, or load stages, read your data pipelines context — it names the one concrete business deliverable your company needs, who it’s for, at what cadence, the exact KPIs it must compute (see its “KPIs to Measure” section), and which mandatory metrics feed them. This is a follow-through on what your telemetry `CONTEXT-company.md` flagged back in section 4, “How These Metrics Connect to the Future” — this is that moment, now spelled out concretely.

Design the pipeline to produce exactly that data deliverable — at the right freshness, granularity, and audit trail. Don’t invent a generic KPI; the one your company needs is already scoped.

This is a new pipeline, not a replacement. The technical telemetry report you built earlier keeps answering technical questions for engineers (volume, errors, latency). This pipeline answers a different question, for a different audience, and its output lives in different tables and different endpoints. Nothing from the earlier project changes.

When you write the pipeline purpose in Phase 2, name the business deliverable you’re targeting and the mandatory metric(s) that feed it. If a stage in your design doesn’t support that deliverable, question whether it belongs in v1.

---

## 🌱 How to Start

2. Explore the `data/` folder in the monorepo — it contains subfolders (`raw/`, `process/`, `pipelines/`, and `eval/`) that you will use throughout this module. Orchestration code will live in `data/pipelines/`; reusable transformation scripts in `data/process/`; HTTP endpoints that query or trigger the pipeline live in `services/` and import from `data/pipelines/` — not the other way around.
3. Create the file `data/pipelines/PIPELINE_DESIGN.md` — that is where your design document goes.
4. Read your `CONTEXT-company.md` from the data pipelines context — its “KPIs to Measure” section names the exact numbers this pipeline must produce, and it also states the audience, cadence, required aggregation, and destination table. The mandatory metrics feeding those KPIs are the ones from your telemetry `CONTEXT-company.md`, already familiar from the earlier milestone.
5. This pipeline’s output does not belong in `telemetry_events`. All new destination tables live under a dedicated `reporting` schema, named `reporting.business_metrics` — and are exposed through a new `services/reporting/` module, kept separate from `services/telemetry/` and the `GET /telemetry/report` endpoint.

> **Note on tooling:** Today you are introduced to Prefect as an orchestration framework — flows, tasks, states, and configuration blocks. Your design document should reflect how you would organize your pipeline using these concepts, even though the code implementation comes over the next days.

---

## 🖥️ What You Need to Do

### Phase 1 — Current state analysis

- Document in a “Current State” section what you already have: the telemetry events captured so far, where they’re stored, and what your existing technical report already answers for engineering.
- Identify the gap: which business question from your `CONTEXT-company.md` is still unanswered by that technical report, and would require a dedicated pipeline?

### Phase 2 — Pipeline design

- Define the purpose of the pipeline in a single concrete sentence: name the specific business deliverable you’re targeting, e.g. “produce the daily rollup that feeds [role]’s weekly executive report”, the KPI(s) it computes from your company’s “KPIs to Measure” section, and the mandatory metric(s) from your telemetry `CONTEXT` it is built on.
- Specify the extraction format: your source is `telemetry_events` plus any other existing domain tables you need — in what format the data arrives, and how often it’s updated.
- Design the data flow with a text or Mermaid diagram showing at least three clearly separated stages: extraction, transformation, and load.
- Describe how you would handle a source that updates existing records rather than always inserting new ones — explain the concrete strategy to avoid duplicates in your specific case.
- Name the new destination table(s) under the `reporting` schema (`reporting.business_metrics`), where this pipeline’s output will live, and the new endpoint(s) in `services/reporting/` that will expose it — explicitly separate from `telemetry_events` and `GET /telemetry/report`.

### Phase 3 — Resilience and idempotency

- Define your idempotency strategy: if the pipeline fails during the load phase and is re-run, explain exactly how you guarantee that already-loaded data is neither corrupted nor duplicated.
- Design your execution log: specify the minimum fields you would record in every run (start time, end time, records processed, status, errors) and explain why each field is necessary to audit the pipeline in production.

### Phase 4 — Mapping to Prefect

- Map your design to Prefect concepts: identify which parts would be flows, which would be tasks, and which states (Running, Completed, Failed) are relevant for your pipeline.
- Indicate which configuration or credentials you would manage as Prefect blocks, for example, the connection to Supabase.

### Phase 5 — Application integration (design only)

- Sketch the new endpoint(s) in `services/reporting/` the business side will use to query the resulting metric(s) and/or trigger a run — kept separate from `services/telemetry/` and the `GET /telemetry/report` endpoint.
- For each endpoint, state which function or flow in `data/pipelines/` it will call — no ETL logic belongs in `services/`.

> ⚠️ **IMPORTANT:** Field names, entity IDs, and domain-specific values in your design must match your company’s domain vocabulary in the monorepo. A generic design that ignores your company’s data model will not be accepted.

---

## ❓ Questions to Help You Design the Pipeline

### Idempotency

#### 1. Duplicates at the source

How do you prevent counting the same action twice in `telemetry_events` and your business aggregates? Which envelope field is your dedupe key, and at which layer?

- See example and hint.

#### 2. Re-run after failure

If the pipeline dies during load with partial data inserted, what happens when you re-run? How do you guarantee the same outcome as a clean run?

- See example and hint.

#### 3. Late events

How do you recompute a published daily business metric when a delayed event arrives, without inflating numbers or losing audit trail?

- See example and hint.

### Observability

#### 1. Silence vs. true absence

How do you tell zero activity from failed capture or a pipeline that never ran? What minimum signals would you record?

- See example and hint.

#### 2. Collection traceability

What traces reconstruct the path event → business report and detect gaps, bursts, or interval drift?

- See example and hint.

#### 3. Growth vs. data loss

If event volume swings day to day, how do you know the business is growing vs. losing or duplicating measurements?

- See example and hint.

### Recoverability

#### 1. Database outage

Where do you resume if the connection drops mid-pipeline? What checkpoint do you persist?

- See example and hint.

#### 2. Frontend buffer

Does buffering offline events in the browser make sense? What risks does it introduce, and which layer should own the retry?

- See example and hint.

#### 3. Transmission retry

How do you design retries on `POST /telemetry` without breaking idempotency? What server response means “already stored, retry”?

- See example and hint.

### Cross-cutting

#### 1. Concurrent runs

What do you observe, how do you avoid race conditions, and how do you recover when cron and a manual trigger from `services/` overlap?

- See example and hint.

---

## ✅ What We Will Evaluate

- The file `data/pipelines/PIPELINE_DESIGN.md` exists in the monorepo and is written in readable Markdown.
- The pipeline purpose is defined in a single concrete sentence that names the business deliverable and KPI(s) from the company’s `CONTEXT-company.md` — not a generic or technical KPI.
- The design does not modify `telemetry_events`, `services/telemetry/analysis.py`, or `GET /telemetry/report` — the new pipeline’s output lives in new tables under a `reporting` schema and is exposed through a new `services/reporting/` module.
- The data flow diagram shows at least three distinct stages: extraction, transformation, load, with the real entity or table names from the company.
- The strategy for handling updates to existing records is documented with a concrete mechanism, e.g. upsert by primary key, last-modified timestamp, control table.
- The idempotency strategy is explicit: it describes what happens on the second run after a load-phase failure, not just what would be desirable.
- The execution log specifies at least five fields with the field name, data type, and justification for why that field is necessary for auditing.
- The Prefect mapping identifies at least two flows and three tasks with concrete names aligned with the pipeline stages.
- The design document’s at least two planned `services/reporting/` endpoints — daily query and manual trigger — and names the `data/pipelines/` functions each will import.
- The design is consistent with the telemetry events and mandatory metrics already defined in the company’s `CONTEXT` file.



# Part 2 of 3 — Implementing a Resilient Business Performance Pipeline

## Milestone 6 — Implementing a Resilient Business Performance Pipeline (2/3)

**Before you start:** Keep your `CONTEXT-company.md` open while you code — it is the source of truth for KPI names, destination table schema, and the endpoint contract you implement. Also have your approved `data/pipelines/PIPELINE_DESIGN.md` from Part 1 ready.

---

## 🎯 The Challenge

The design document is approved. Now it’s time to build it — a pipeline that reads from `telemetry_events` and produces the business-facing KPIs you scoped in Part 1, exactly as named in your `CONTEXT-company.md`.

Your existing technical telemetry system (`telemetry_events`, `services/telemetry/analysis.py`, `GET /telemetry/report`) is not part of this work — it stays untouched, still serving engineering.

There is a fundamental difference between a script that works on your machine and a pipeline that can run in production unattended: **resilience**.

> **Implementation Ticket — Resilient Business Performance Pipeline**
>
> The design is approved. Leadership wants to see this pipeline running, not just documented. Non-negotiable requirements before handoff to production:
>
> - The pipeline must tolerate partial failures without interrupting the entire execution.
> - Tasks that touch external services must have retries configured.
> - The pipeline must be runnable as a script from the command line.
> - If a task has already run successfully in the last hour, it must not repeat unnecessarily.
>
> Starting point: your `data/pipelines/PIPELINE_DESIGN.md` from the previous day. Implement what you designed — reading from telemetry, writing to the new business reporting table you scoped, nothing about the existing technical report changes.

---

### What makes a pipeline resilient?

A resilient pipeline is not one that never fails — it is one that fails well. In Prefect, that means three concrete things:

- **Partial failure tolerance:** a failing task does not bring down the entire flow. Prefect distinguishes between critical tasks, whose failure should stop everything, and optional tasks, whose failure should be logged and allow the flow to continue.
- **Smart retries:** tasks that interact with external services, such as databases and APIs, are configured with `retries` and `retry_delay_seconds` to absorb transient failures without human intervention.
- **Result caching:** if a task already produced a valid result recently, Prefect can reuse it rather than repeating the computation. This is especially useful for expensive transformations.

---

## 🌱 How to Start

2. Open your `data/pipelines/PIPELINE_DESIGN.md` — that document is your specification. Implement what you designed.
3. Keep your `CONTEXT-company.md` from the data pipelines context open while you code: it’s the source of truth for the exact KPI names, its “KPIs to Measure” section, the destination table schema, and the endpoint contract you’re implementing. The event fields you’re extracting from are the ones your telemetry `CONTEXT-company.md` already defined as mandatory.
4. Write your pipeline code in `data/pipelines/`. The main entry point must be named `data/pipelines/pipeline.py`. Use `data/raw/` for input data and intermediate files, `data/process/` for reusable transformation scripts, and `data/eval/` for pipeline validation outputs.
5. The extraction task reads from `telemetry_events` and any other domain tables you need — read-only. The load task writes to the new `reporting.business_metrics` table you designed in Part 1. Do not write back into `telemetry_events` and do not modify `services/telemetry/analysis.py`.
6. Any endpoint that exposes or triggers the pipeline, for example to query the status of the last run or launch a run manually, must be implemented in `services/reporting/`, a module separate from `services/telemetry/`, importing functions and flows from `data/pipelines/` as needed.
7. Install Prefect 3 in your environment:

```bash
uv add "prefect>=3"
```

---

## 🖥️ What You Need to Do

### Phase 1 — Flows and tasks

- Implement the pipeline as one or more Prefect flows (`@flow`) following the stage structure from your design: extraction, transformation, and load as a minimum.
- Each stage must be an independent task (`@task`) with explicit inputs and outputs.
- If your pipeline has optional steps, for example notifications or secondary exports, invoke them with `return_state=True` so that a failure in them does not interrupt the main execution.

### Phase 2 — Resilience

- Add `retries` and `retry_delay_seconds` to every task that interacts with external services, such as databases and APIs. Justify the number of retries chosen in a comment.
- Handle at least one task failure explicitly in the flow using `return_state=True` rather than letting it propagate automatically.
- Add caching (`cache_key_fn`, `cache_expiration`) to at least one expensive transformation task. Explain in a comment what defines the cache key and how long it is valid.

### Phase 3 — Idempotency

- The load phase must be idempotent: if the pipeline runs twice over the same date range, the result in your `reporting.business_metrics` table must be identical after both runs. Implement the strategy you documented in your design, such as an upsert, control table, timestamp, or another mechanism. The unique constraint from your `CONTEXT-company.md` schema is what your upsert should key off of.
- Record in the database or in a log file the minimum execution metadata for each run: start time, end time, records processed, final status, and any captured errors.

### Phase 4 — Script-based execution

- Ensure `data/pipelines/pipeline.py` can be executed directly as a CLI script, for example with an:

```python
if __name__ == "__main__":
```

block that invokes the main flow.

- Verify the full pipeline runs without errors:

```bash
python data/pipelines/pipeline.py
```

- Document the intended schedule for your company’s reporting cycle in `data/pipelines/PIPELINE_DESIGN.md` and the run command in a comment or in the same design document.

### Phase 5 — Backend endpoints

- In `services/reporting/`, implement at least two endpoints related to this pipeline: one to query the status and metadata of the last run, and one to trigger a manual flow run. Keep them in their own module, separate from `services/telemetry/`.
- The endpoints must import flows or functions from `data/pipelines/` — do not duplicate pipeline logic in `services/`.
- The endpoints should follow the same authentication conventions and response structure as the rest of your API, and the KPI query endpoint’s response shape must match the contract in your `CONTEXT-company.md`.

> ⚠️ **IMPORTANT:** Flow names, task names, and field names must match what is defined in `data/pipelines/PIPELINE_DESIGN.md` and your `CONTEXT-company.md` from the data pipelines context. KPIs and schema must remain consistent, in turn, with the event fields already defined in your telemetry `CONTEXT-company.md`. A generic implementation that ignores your company’s data model will not be accepted.

---

## ✅ What We Will Evaluate

- The file `data/pipelines/pipeline.py` exists and defines at least one flow with three or more tasks.
- At least one task has `retries` configured with a value greater than zero and a comment justifying the number chosen.
- At least one optional task is invoked with `return_state=True` and the flow continues executing when that task fails.
- At least one transformation task has caching configured with `cache_key_fn` and `cache_expiration`.
- The load phase is idempotent: running the pipeline twice over the same date range does not produce duplicates in the `reporting.business_metrics` table.
- Each pipeline run records at least five metadata fields — start time, end time, records processed, status, and errors — in the database or in a structured log file.
- `python data/pipelines/pipeline.py` runs the full ETL flow without errors.
- The run command is documented in `data/pipelines/PIPELINE_DESIGN.md` or in-line comments.
- The pipeline writes to the new `reporting.business_metrics` table from your `CONTEXT-company.md` — `telemetry_events` and `services/telemetry/analysis.py` are untouched.
- At least one endpoint exists in `services/reporting/` that returns the metadata of the last pipeline run: status, start time, end time, records processed.
- At least one endpoint exists in `services/reporting/` that triggers a manual run, importing the function from `data/pipelines/` without duplicating the logic.
- The KPI values produced match the definitions in your `CONTEXT-company.md`’s “KPIs to Measure” section — not a reinterpretation of them.
- The implemented design is consistent with `data/pipelines/PIPELINE_DESIGN.md` — the stages, entities, and resilience strategies described there are reflected in the code.


---

# Part 3 of 3 — Business Performance Pipeline Enhancement: Subflows and Tests

## Milestone 6 — Business Performance Pipeline Enhancement: Subflows and Tests (3/3)

**Before you start:** Make sure you have completed **Part 2 of Milestone 6** — this project builds directly on `data/pipelines/pipeline.py` implemented in the previous session. Keep your `CONTEXT-company.md` open — KPI names, schema, and stakeholder audience come from there.

---

## 🎯 The Challenge

> 📌 You are building on your own fork of the company’s **monorepo** selected at the beginning of the course — not on a new repository.

This is **Part 3 of Milestone 6 — Telemetry and Data Pipelines**. Your business performance pipeline already works: it reads from `telemetry_events` and produces the KPIs leadership asked for — the ones named in your `CONTEXT-company.md` — without touching the existing technical telemetry system.

Today you bring it to production level: you refactor the main flow into reusable subflows, add unit tests that validate the behavior of transformation tasks, ensure the pipeline runs directly from the command line, and — this is the part leadership actually cares about — put those KPIs in front of a dashboard someone can read.

> **Enhancement Ticket — Pipeline to Production**
>
> The basic pipeline is ready. Before the final handoff to the operations team, I need four more things:
>
> 1. The main flow is growing — refactor it into subflows so that each phase is independent, testable, and reusable.
> 2. I need unit tests for the transformation tasks. If a test fails, I want to know before the pipeline reaches production, not after.
> 3. The pipeline must be runnable as a script. When I execute `python data/pipelines/pipeline.py`, the full ETL flow must complete without errors.
> 4. I need a dashboard. Nobody on the leadership team is going to query an endpoint — put the KPIs somewhere they can actually look at them.
>
> Starting point: `data/pipelines/pipeline.py` from the previous session.

---

### Why subflows

A flow that grows without structure ends up being as hard to maintain as the script it replaced. Subflows apply the DRY principle at the orchestration level: each phase of the pipeline — extraction, transformation, load — becomes an independent flow that can be executed, monitored, and reused separately. The main flow coordinates them but does not contain their logic.

---

## 🌱 How to Start

2. Open `data/pipelines/pipeline.py` — that is your starting point.
3. Keep your `CONTEXT-company.md` at hand: subflow, task, and test names should reflect the KPI names from its “KPIs to Measure” section and the schema you implemented — not generic labels.
4. Keep the existing folder structure:
   - `data/pipelines/` for flows and subflows
   - `data/process/` for transformation logic
   - `data/raw/` for input data
   - `data/eval/` for validation outputs
5. Unit tests go in `tests/pipelines/` at the root of the monorepo.
6. The dashboard page goes in `uis/backoffice/`, fetching from the `services/reporting/` endpoint you already built in Part 2.
7. Ensure Prefect 3 is installed from Part 2:

```bash
uv add "prefect>=3"
```

---

## 🖥️ What You Need to Do

### Phase 1 — Refactoring into subflows

- Split the main flow into at least three subflows (`@flow`) that correspond to the stages from your design:
  - one for extraction from `telemetry_events` and any other domain tables
  - one for transformation
  - one for load into your `reporting.business_metrics` table
- The main flow invokes them in sequence.
- Each subflow must have explicit inputs and outputs — do not rely on global variables between subflows.
- If you have optional steps such as notifications or secondary exports, extract them as subflows too and invoke them with `return_state=True` from the main flow.

### Phase 2 — Unit tests

- Create the file `tests/pipelines/test_pipeline.py` with unit tests for at least three transformation tasks — the ones that compute the KPIs from your `CONTEXT-company.md`.
- Each test must verify the task’s behavior in isolation; it must not depend on a database or external APIs. Use in-memory test data shaped like your telemetry events, according to your `CONTEXT-company.md`.
- Include at least one test that verifies the defensive behavior of a task against invalid or malformed input, for example:
  - a null field where none is expected
  - an incorrect type
- Include at least one test that asserts a computed KPI value matches the definition in your `CONTEXT-company.md` for a known, hand-calculated input.
- The tests must pass with:

```bash
python -m pytest tests/pipelines/test_pipeline.py
```

### Phase 3 — Script-based execution

- Ensure `data/pipelines/pipeline.py` can be executed directly as a CLI script, for example with an:

```python
if __name__ == "__main__":
```

block that invokes the main flow.

- Verify the full pipeline runs without errors:

```bash
python data/pipelines/pipeline.py
```

- Document the run command in a comment or in `data/pipelines/PIPELINE_DESIGN.md`.

### Phase 4 — Business dashboard (mandatory)

Your pipeline produces KPIs — but a table nobody looks at is not a deliverable. This phase is not optional: leadership needs to actually see the numbers, not query an endpoint with `curl`.

- Build a page in `uis/backoffice/`, for example `/reporting`, that fetches your `services/reporting/` endpoint and renders every KPI from your `CONTEXT-company.md`’s “KPIs to Measure” section.
- A chart or a table per KPI is enough.
- Label each KPI clearly with the same name it has in your `CONTEXT-company.md`, and show the period the data covers, such as week or month, according to your cadence.
- This dashboard is business-facing, not a developer tool: it should be legible to the stakeholder named in your `CONTEXT-company.md`, such as the CEO or department head, without needing anything translated or explained.
- No visual polish is required — a working, correctly labeled view of real data from `reporting.business_metrics` is the goal.

> ⚠️ **IMPORTANT:** Subflow names, task names, and test names must follow the same domain vocabulary defined in `data/pipelines/PIPELINE_DESIGN.md` and your `CONTEXT-company.md`. A subflow named `extract_data` is not acceptable if your company has concrete entities and KPI names — name it after the actual business metric this pipeline produces.

---

## 🔵 Additional Activity — Extra Enhancements from Your Design Questions

Go back to the “Questions to Help You Design the Pipeline” section from Part 1. If, while answering those questions, you identified resilience or observability enhancements beyond what Phases 1–3 already cover — for example:

- a heartbeat plus silence alert
- a concurrency lock for overlapping runs
- an `Idempotency-Key` pattern for retries

—and you have not implemented them yet, this is the place to do it.

- For each enhancement you add, note in `data/pipelines/PIPELINE_DESIGN.md` which question it answers and why you prioritized it.
- This is optional — only pick it up if your own design actually flagged something worth building. Don’t invent an enhancement just to check a box.

---

## ✅ What We Will Evaluate

- The main flow in `data/pipelines/pipeline.py` invokes at least three subflows (`@flow`) instead of containing all logic directly.
- Each subflow has explicit inputs and outputs and can be executed independently.
- The file `tests/pipelines/test_pipeline.py` exists and contains at least three unit tests for transformation tasks.
- At least one test verifies the defensive behavior of a task against invalid input.
- At least one test validates a KPI’s computed value against its definition in `CONTEXT-company.md`.
- `python -m pytest tests/pipelines/test_pipeline.py` passes without errors.
- `python data/pipelines/pipeline.py` runs the full ETL flow without errors.
- The run command is documented in `data/pipelines/PIPELINE_DESIGN.md` or inline comments.
- Subflow names, task names, and test names reflect the domain vocabulary and KPI names from `CONTEXT-company.md`.
- `telemetry_events` and `services/telemetry/analysis.py` remain unmodified throughout the refactor.
- A dashboard exists in `uis/backoffice/` that displays every KPI from `CONTEXT-company.md`’s “KPIs to Measure” section, correctly labeled and sourced from your `services/reporting/` endpoint.
- The dashboard is legible to a non-technical business stakeholder, not just to another engineer.

---
