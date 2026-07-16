#!/bin/sh
# Least-privilege login for the reporting worker's startup guard.
#
# The guard only reads pg_catalog (pg_extension, pg_tables), which is readable by
# PUBLIC, so CONNECT is the entire privilege set it needs. It deliberately gets no
# SELECT on any table: unlike prefect_backup, it must not be able to read Prefect
# state. Keep these two roles separate — a guard credential is handed to a
# long-running application worker, a backup credential is not.
set -eu

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=guard_password="$PREFECT_GUARD_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE prefect_guard LOGIN PASSWORD %L', :'guard_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prefect_guard') \gexec
SELECT format('ALTER ROLE prefect_guard PASSWORD %L', :'guard_password') \gexec
GRANT CONNECT ON DATABASE prefect TO prefect_guard;
SQL
