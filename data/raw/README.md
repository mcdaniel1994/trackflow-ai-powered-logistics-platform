# `data/raw` folder

This folder is intended for **raw data** related to the company: dumps, exports, sample files, event samples, or untransformed datasets.

- **Main purpose**: serve as a landing zone or reference for original data before pipelines process it.
- **Recommendation**: document each dataset’s origin, format, expected size, privacy/PII considerations, and how it is versioned (ideally avoiding sensitive data in the repository).

## `trackflow_sales.csv`

This 120-row consolidated monthly revenue dataset covers 2016-01 through 2025-12 and contains no
PII. It is generated rather than observed: the owner approved that explicit deviation because the
assignment's claimed source file did not exist and production has no revenue dimension. Regenerate
or validate it deterministically with `scripts/generate_trackflow_sales.py` (seed 42).
