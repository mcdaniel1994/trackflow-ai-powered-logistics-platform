# GATE-8a cache mechanism decision

**Executed:** 2026-07-14

**Decision:** Use the application-managed boto3 cache in `cache.py`.

**Infrastructure:** Local moto S3/R2 emulator only; no real bucket, credentials, Prefect API,
Prefect database, or external system was used.

## Why this mechanism was selected

Current Prefect task documentation says a block instance supplied as `result_storage` must be
saved before decorator import-time use. The result-storage guide also describes shared reuse in
terms of a saved block and the same Prefect API. That persistence requirement conflicts with
TrackFlow's approved Prefect-as-library boundary, which has no permanent Prefect API or database.

- Prefect task API: <https://docs.prefect.io/v3/api-ref/python/prefect-tasks>
- Prefect result persistence: <https://docs.prefect.io/v3/advanced/results>

The approved fallback therefore owns only the S3-compatible object read/write mechanics through
boto3. Prefect still owns flow/task orchestration and retries. PostgreSQL remains the sole durable
business and run-audit system of record.

## Executed proof

```bash
uv run --project data --extra dev \
  python data/pipelines/business_performance/spikes/r2_cache_spike.py
```

Observed result:

```json
{
  "mechanism": "application-managed-boto3",
  "first": {"cache_hit": false, "computed": true, "row_count": 1},
  "second": {"cache_hit": true, "computed": false, "row_count": 1}
}
```

The script starts an emulated private S3 endpoint, launches two fresh Python worker processes, and
uses the same content-derived key. The first process computes and writes
`prefect-results/<sha256>.json`; the second reads that object and does not call its compute
function. `PREFECT_API_URL` is empty in both workers.

## Accepted guarantees

- One-hour TTL is enforced from the object envelope at read time.
- Source content digest, SKU dimensions, pipeline version, evaluation version, target/reset window,
  recompute parameter, and optional force-refresh nonce all participate in the SHA-256 key.
- Reads fail open to recomputation. Writes retry twice, then log a safe reason and skip caching.
- Load/publication and run-row transitions are never cached.
- Missing R2 configuration disables caching without affecting pipeline correctness.
- The Prefect transformation task retains `cache_key_fn` and `cache_expiration=timedelta(hours=1)`.

GATE-8a is technically accepted. GATE-8b remains open and owner-executed before Phase 11: private
R2 provisioning, least-privilege token, one-day lifecycle rule, and runner-only secret injection.
