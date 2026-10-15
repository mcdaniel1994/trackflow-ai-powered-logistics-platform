# Backoffice database connection budget

**Engagement:** 6 connection reliability correction, approved October 15, 2026.
**Status:** Backend Phase 1 reviewed; owner approved continuation. Both corrective phases are
implemented and verified locally; owner approved commit/push. Separate production approval pending.
No production change performed.

## Configuration and capacity

The runtime role's Supavisor session cap is 15, separately from Postgres's 60-connection ceiling.
Idle application-pooled sessions consume capacity. Both Compose files pin these values:

| Service | `DATABASE_POOL_SIZE` | `DATABASE_MAX_OVERFLOW` | Maximum |
|---|---:|---:|---:|
| central-api | 3 | 0 | 3 |
| operations-feed | 2 | 1 | 3 |
| reporting-worker | 2 | 3 | 5 |
| maintenance-worker | 1 | 0 | 1 |
| RFP checkpoints inside Central API | minimum 0 | not applicable | 1 |
| **Total** | | | **13** |

All checkouts use `DATABASE_POOL_TIMEOUT_SECONDS=5`. SQLAlchemy defaults are 3/0 for Central API
and 2/3 for reporting; workers receive explicit Compose settings. Size must be >=1, overflow >=0,
their sum <=15, and checkout timeout finite and in (0,30]. The RFP pool is lazy, capped at one,
has at most 16 waiters, closes idle sessions after 60 seconds and closes on app shutdown. It borrows
per database operation rather than across graph execution. Migration provisioning is unchanged.

Connections request `application_name=trackflow:<service>` (RFP: `rfp-checkpoints`). Supavisor may
replace this label; do not promise database-side attribution. Startup `database_pool_configured`
and timeout `database_pool_exhausted` logs provide fixed service names and numeric limits/counts.
Checkpoint and lock failures log fixed events/types; driver reconnect text is redacted. Never add
query contents, connection strings, payloads or credentials to diagnostics.

Lock helpers use dedicated autocommit connections, finish acquisition bookkeeping, preserve the session lock and explicitly unlock
before returning a reusable connection. Uncertain cleanup invalidates the physical session. The
feed checks original backend/lock ownership before every write tick and exits on loss; its restart
policy recovers it. Pool recycle is evaluated at checkout, not while a session is borrowed.

## Local acceptance

Use disposable PostgreSQL on localhost port 55432; fixtures refuse other hosts/ports. Disable
demo feature flags and blank provider credentials. Do not source production environment files.

The standalone gate `services/central-api/tests/test_connection_workload.py` skips in normal suites.
Set `TRACKFLOW_CONNECTION_SOAK_SECONDS=600`, the verified disposable `DATABASE_URL`,
`RAG_ENABLED=false`, `AGENTS_ENABLED=false`, `RFP_ENABLED=false`,
`PUBLIC_SUPPORT_ENABLED=false`, empty `OPENAI_API_KEY`/`DEEPSEEK_API_KEY`, and
`RAG_GENERATION_MODEL=deepseek-chat`, then run:

```sh
uv run --project services/central-api --extra dev pytest \
  services/central-api/tests/test_connection_workload.py -q -s
```

It runs two authenticated four-request dashboard clients, real inventory generation, direct-SQL
reporting/renewal/heartbeat/scheduling, periodic maintenance checks and checkpoint reads. Control
and feed cadences are accelerated for contention; dashboard cadence stays 20 seconds. An extra
local observer connection is excluded from runtime counts. Phase 2 verifies browser recovery;
this backend gate does not claim browser/UI coverage.

### October 15 local verification evidence

| Gate | Result |
|---|---|
| Central API full suite | 520 passed, 1 skipped; 91.56% coverage (prior recorded baseline 91.41%) |
| Data pipelines full suite | 158 passed, 1 existing skip; 92.50% coverage (prior recorded baseline 92.16%) |
| Standalone combined workload | Passed in 600.29 seconds; 2,327 samples; peak 11 runtime connections, below the 13 budget |
| Workload failure/transaction checks | No checkout exhaustion, dashboard request failures, reporting/maintenance operation failures, failed reports or idle-in-transaction advisory-lock holder |
| Release safety | 17 tests passed, including both Compose budget/single-process contracts |
| Typing | Central API 109 source files and data 25 source files pass mypy |
| Lint | Ruff passes for Central API, data pipelines and release checks |
| Builds | Both wheel/sdist builds pass; new helper included; no `.env` files in either wheel |
| Database schema | Existing local migrations applied for setup; `alembic check` reports no new upgrade operations; no migration added |
| Compose | Local and production configuration validation pass without deployment |
| Supply chain | `pip-audit` reports no known vulnerabilities; psycopg-pool remains 3.3.1; LGPL register updated for direct usage |

The ordinary Central API skip is the opt-in ten-minute workload, which passed separately above.
Additional regressions cover simultaneous cold starts sharing one API engine, one-connection RFP
decision/trace persistence, bounded checkpoint contention/recovery, real lease/heartbeat/scheduler
overlap within the five-connection reporting pool, lock release/loss, malformed limits and safe logs.
Process-engine initialization is serialized; `lru_cache` alone cannot enforce one cold-start pool.
Both process-owned API pools close on application shutdown.

Commands and evidence were local only. Test provider keys were empty or synthetic and model behavior
was mocked. The disposable database was created specifically for this verification; no production
data, settings or sessions were changed. At that verification checkpoint no commit, push, paid provider call or deployment had occurred.
The owner subsequently approved commit/push; production remains unchanged.
Reviewed database, authentication, telemetry, testing, error-handling, observability,
production-readiness and licensing standards. Phase 2 acceptance also passed: Back Office 229 tests
(previous 202), clean lint/types/build, and one standalone mocked browser journey verifying fresh
login, partial recovery, authentication refresh, retained stale data, recovery and range clearing.
Desktop/mobile screenshots were inspected. No frontend numeric coverage gate/provider is configured;
existing tests are preserved and new polling/status failure branches are tested.

## Later production preflight and rollout

These are review instructions, not authorization to execute:

1. Privately record the deployed immutable tag and effective Compose revision/configuration.
   Verify one Uvicorn worker and one replica per consumer, the 15-slot cap and all runtime engines.
   Local development must use disposable storage.
2. Inventory roles/states/transaction ages using aggregate-only read-only queries. Attribute
   ambiguous sessions through safe service diagnostics or host process inspection. Do not terminate
   unidentified sessions or the old transaction based on age alone.
3. Include auxiliary clients, operator checks and old/new containers in the total. A topology
   mismatch or possible runtime total >13 blocks release. The two spare slots do not authorize
   uncontrolled deployment overlap.
4. After explicit approval, use the established immutable-image GitHub/Coolify release path.
   If replacement cannot preserve the budget, prepare an approved maintenance stop/start that
   drains old consumers before replacements. Do not assume `up -d` guarantees zero overlap.
5. Verify fresh login, all dashboard reads, Phase 2 partial-failure recovery, successful reports
   and renewal, single feed leadership, runtime connections <=13 and no repeated session-cap
   errors or idle-in-transaction lock holders. Record reporting verification separately from core
   readiness and preserve the existing rollback/readiness separation.

## Recovery boundaries

Image rollback does not restore Compose configuration. Preserve both revisions before release
and review their compatibility. Old images can ignore these settings and reproduce the outage;
reverting the tag does not necessarily preserve the budget. Account for old limits and overlap,
with an approved workload drain/reduction if needed. Restore a reviewed Compose revision or deploy
a forward correction through the release procedure. Never downgrade/reset the database for this
application-only fix. No pool-limit increase or transaction-mode switch is part of this plan.

## Dashboard behavior and local browser acceptance

Operations Overview and Operations → Fulfilment use `useResourcePolling`; other dashboards retain
`useAutoRefresh`. Each resource renders independently, retaining its last success on later failure.
Unavailable totals use `—`; successful empty responses use zero or the existing empty-state text.
Errors appear beside the affected section. Retained values are marked stale with their local-time
last-success timestamp after a failed attempt or 60 seconds without success. Date-range changes
clear all old values immediately, including when returning to an earlier range.

Healthy resources poll every 20 seconds after completion. Only network failures, bounded browser
timeouts, and HTTP 502/503/504 receive transient retries: 2/4/8/16/30 seconds, capped at that base
with ±20% jitter (maximum actual delay 36 seconds). Success resets the backoff. Other HTTP errors
stop automatic polling for that resource; its message asks the operator to refresh. Visibility
restoration also requests fresh data. There is at most one active request per resource; hidden tabs
cancel active reads and timers, and unmount/range changes abort and ignore obsolete completions.
Browser reads have a 20-second deadline above the existing 15-second BFF timeout. Cancellation
passes through the existing authenticated fetch helper, preserving its one-time 401 refresh flow.
No write retries were added.

The aggregate indicator says Live only if every resource's latest completed attempt succeeded and
all successes are less than 60 seconds old. Otherwise it shows Connecting, Partial data, or
Unavailable, with retrying when transient retry scheduling is active. A green Live badge is no
longer shown for partial/failed reads on these two views.

Reproduce the dedicated local browser journey after the production build:

```sh
npm run type-check --workspace trackflow-backoffice
npm run lint --workspace trackflow-backoffice
npm run test --workspace trackflow-backoffice
npm run build --workspace trackflow-backoffice
npm exec --workspace trackflow-backoffice playwright test -- \
  --config playwright.connection-recovery.config.ts
```

The explicit config runs the standalone production output on localhost:3016, with disposable
Identity/Central API fixtures on localhost:18886. It copies static/public assets into ignored build
output, matching the Docker image layout. It never uses production accounts, live storage or model
providers. The default browser suite excludes this fixture-specific journey. Unit tests cover
visibility, cancellation, bounded in-flight reads/timeouts, every backoff step and jitter bounds,
non-transient statuses, scope changes and late completions; rendered tests distinguish failure
placeholders from genuine empty zeroes and exercise stale/live transitions.

## Immutable-image release worksheet (owner approval required)

Prepare and review the following values before approving a deployment:

| Record | Required evidence |
|---|---|
| Candidate | Reviewed commit SHA; immutable `sha-<40 lowercase hex>` tag, never `main` or `latest` |
| Image set | Successful release checks and Linux AMD64 manifests/digests for Identity, Central API, Back Office and MCP at that exact tag |
| Effective configuration | Candidate `compose.coolify.yaml` revision plus privately stored effective settings; explicit caps 3/0, 2/1, 2/3, 1/0 and checkout timeout 5 |
| Current recovery point | Prior immutable image tag/digests and prior effective Compose revision/settings, captured before changing either |
| Topology | One replica/process/engine per listed consumer; API includes one extra checkpoint pool capped at 1; auxiliary runtime clients enumerated |
| Capacity | Supavisor session cap still 15 for runtime role/database, peak runtime budget <=13 including replacement overlap |
| Schema/other features | Compare deployed and candidate revisions and feature flags; no pending schema or unrelated feature enablement implicitly approved |
| Replacement | Approved drain and stop/start sequence with expected interruption, or a demonstrated overlap calculation that stays within budget |
| Approval | Explicit owner approval naming tag, Compose revision, replacement sequence and recovery procedure |

`container-images.yml` runs release checks and publishes all four commit-pinned images. A main
branch publication also queues `deploy-production.yml` behind the GitHub Production environment;
do not approve that job as part of local implementation review. The owner approved a feature-branch commit/push after local review; its commit SHA is the
candidate identity. Registry publication and production approval remain future steps, with
unrelated existing edits kept out of this correction's commit.

The deployment workflow updates `TRACKFLOW_IMAGE_TAG`, not the effective Compose settings. Merely
rolling the image cannot apply this fix's worker budgets: arrange the approved Compose revision
update explicitly and verify the rendered configuration on the host before starting consumers.
Its normal `release` mode invokes the migration runner. This correction adds no migration and does
not authorize production migrations; if the candidate contains pending migrations, stop for a
separately reviewed release decision. Do not select `image-rollback` as a workaround for bypassing
release checks. Compare the actual deployed schema first, rather than relying on historical docs.

After approval, prefer a short, planned drain/stop/start if full old/new overlap is unbudgeted:
stop admitting application traffic; stop feed and maintenance work; allow reporting's current
claim to finish or follow its existing approved recovery procedure; shut down old API/reporting
processes and verify their identified connections/locks are released. Start only the reviewed
replacement set with the pinned caps. Keep Identity storage intact. Do not run ad-hoc pool clients,
operator SQL shells using the runtime role, migration/seed profiles or parallel old/new replicas
outside the calculation. If sessions remain unattributed, stop and investigate instead of killing
them. Two headroom slots cannot absorb a second complete 13-slot fleet.

Post-deployment acceptance must be recorded separately from local verification:

1. Fresh login in a clean browser; Overview and Fulfilment display real responses without manual
   refresh. Confirm all four Overview reads and both Fulfilment reads return successfully.
2. Use a browser-local request interception/offline exercise to fail one read (no production
   dependency outage). Healthy sections must stay visible; stale values/timestamps and retry status
   appear, then recover automatically after removing interception. Check a new date range, hidden
   tab/resume, and an empty range. Do not fabricate business activity to test this.
3. Observe runtime sessions and transaction ages across at least ten minutes with two dashboard
   clients plus normal worker activity. Require <=13 runtime sessions, no repeated
   `EMAXCONNSESSION`, `ECHECKOUTFAILED` or pool-exhaustion events, and no idle-in-transaction lock
   holders. Supavisor can mask application names: combine aggregate database evidence with bounded
   service logs and actual process counts. Never export SQL text or connection strings.
4. Verify one feed leader, advancing canonical activity, successful reporting publication, healthy
   renewal/heartbeats and scheduler, and maintenance health. Core readiness alone does not prove
   reporting health. No paid RFP/AI calls are necessary for this verification.
5. On an acceptance failure, stop rollout and use the reviewed recovery point. Recalculate the
   prior image's actual pool sizes before restarting it: older images may ignore the new limits.
   Restore image and Compose settings together only if their combined budget is safe; otherwise
   use an approved reduced-workload/forward correction. Do not reset data or downgrade the schema.
