# `data/process` folder

This folder contains **processed/intermediate data** and/or artifacts produced by pipelines (for example: clean datasets, features, aggregates, intermediate tables, or transformation outputs).

- **Main purpose**: clearly separate “raw” data from data ready for analysis, modeling, or app consumption.
- **Recommendation**: document which pipeline produces each artifact, its schema, refresh cadence, and how quality is validated (checks, constraints, data tests).

## Business performance

`business_performance/weekly_kpis.py` contains the Engagement 6 pure transform layer: warehouse
vocabulary mapping, weekly KPI assembly, canonical source-content digests, explicit zero rows, and
reset-aware recomputation decisions. It performs no I/O and is validated by
`tests/pipelines/test_pipeline.py`.
