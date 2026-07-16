#!/bin/sh
# Prove Prefect is backed by the migrated PostgreSQL database rather than a
# SQLite fallback. A missing `flow_run` table or `pg_trgm` extension means the
# server did not migrate against this database.
#
# This runs as a bounded retry loop, not a single shot: prefect-server's
# /api/health returns 200 as soon as its API binds, which does not prove the
# first-boot Alembic migration finished creating `flow_run`. A single check
# races that window and reports a false failure.
#
# Every exit emits a fixed token so a failure names itself instead of being
# inferred from an opaque exit code.
set -eu

: "${PGPASSWORD:?required}"
PGHOST="${PGHOST:-prefect-postgres}"
# Defaults to the CONNECT-only guard role: these are catalog reads, so this needs
# no access to Prefect state and must not use the superuser credential.
PGUSER="${PGUSER:-prefect_guard}"
PGDATABASE="${PGDATABASE:-prefect}"
TIMEOUT="${PREFECT_GUARD_TIMEOUT_SECONDS:-60}"
INTERVAL="${PREFECT_GUARD_INTERVAL_SECONDS:-2}"

fail() {
  printf 'prefect_postgres_guard=failed reason=%s elapsed_seconds=%s\n' "$1" "$2"
  exit 1
}

count() {
  psql -h "$PGHOST" -U "$PGUSER" -d "$PGDATABASE" -tAc "$1" 2>/dev/null || printf 'error'
}

elapsed=0
last='unreachable'
while [ "$elapsed" -lt "$TIMEOUT" ]; do
  flow_run="$(count "SELECT count(*) FROM pg_tables WHERE schemaname='public' AND tablename='flow_run'")"
  trgm="$(count "SELECT count(*) FROM pg_extension WHERE extname='pg_trgm'")"

  if [ "$flow_run" = 'error' ] || [ "$trgm" = 'error' ]; then
    last='database_unreachable'
  elif [ "$trgm" != '1' ]; then
    # pg_trgm is created by the image-baked init file and reapplied by the
    # bootstrap; its absence means neither ran against this volume.
    last='pg_trgm_missing'
  elif [ "$flow_run" != '1' ]; then
    # Retryable: the server may still be migrating.
    last='flow_run_table_missing'
  else
    printf 'prefect_postgres_guard=complete elapsed_seconds=%s\n' "$elapsed"
    exit 0
  fi

  sleep "$INTERVAL"
  elapsed=$((elapsed + INTERVAL))
done

fail "$last" "$elapsed"
