#!/bin/sh
set -eu

psql --set=ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=backup_password="$PREFECT_BACKUP_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE prefect_backup LOGIN PASSWORD %L', :'backup_password')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'prefect_backup') \gexec
SELECT format('ALTER ROLE prefect_backup PASSWORD %L', :'backup_password') \gexec
GRANT CONNECT ON DATABASE prefect TO prefect_backup;
GRANT USAGE ON SCHEMA public TO prefect_backup;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO prefect_backup;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO prefect_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE prefect IN SCHEMA public GRANT SELECT ON TABLES TO prefect_backup;
ALTER DEFAULT PRIVILEGES FOR ROLE prefect IN SCHEMA public GRANT SELECT ON SEQUENCES TO prefect_backup;
SQL
