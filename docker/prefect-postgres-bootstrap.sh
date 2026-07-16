#!/bin/sh
set -eu

: "${POSTGRES_USER:?required}"
: "${POSTGRES_DB:?required}"
: "${PREFECT_BACKUP_DB_PASSWORD:?required}"
: "${PREFECT_GUARD_DB_PASSWORD:?required}"

# PostgreSQL only runs /docker-entrypoint-initdb.d for an empty data directory.
# Reapply these idempotent prerequisites on every deployment so an existing
# volume can recover when an earlier initialization was incomplete.
psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --file=/docker-entrypoint-initdb.d/10-pg-trgm.sql

/docker-entrypoint-initdb.d/20-backup-role.sh
/docker-entrypoint-initdb.d/30-guard-role.sh

printf '%s\n' 'prefect_postgres_bootstrap=complete'
