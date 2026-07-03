# Supabase Migrations and Recovery

## Safety boundary

Do not execute this runbook against production without explicit approval that
names the target, confirms the backup, and accepts the recovery path.

## Role bootstrap template

Run as the Supabase administrative role, replacing placeholders through a
secret-safe client:

```sql
CREATE ROLE trackflow_runtime LOGIN PASSWORD '<runtime-secret>';
CREATE ROLE trackflow_migration LOGIN PASSWORD '<migration-secret>';
GRANT CONNECT ON DATABASE postgres TO trackflow_runtime, trackflow_migration;
GRANT USAGE, CREATE ON SCHEMA public TO trackflow_migration;
GRANT USAGE ON SCHEMA public TO trackflow_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO trackflow_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO trackflow_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE trackflow_migration IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trackflow_runtime;
ALTER DEFAULT PRIVILEGES FOR ROLE trackflow_migration IN SCHEMA public
  GRANT USAGE ON SEQUENCES TO trackflow_runtime;
```

`MIGRATION_DATABASE_URL` uses the DDL role. `DATABASE_URL` and all seeds use
the DML role. Both require TLS and direct `:5432` when reachable, otherwise
Supavisor Session `:5432` using the dashboard-provided username.

## Migration procedure

1. Confirm project ref, region, role, current Alembic revision, and approved
   maintenance window.
2. Create an encrypted off-site `pg_dump` and verify it can be read.
3. Test `alembic upgrade head` against a disposable restored copy.
4. Run the explicit `central-api-migrate` one-off.
5. Verify Alembic head, constraints, runtime-role CRUD, and Central API health.
6. Keep incidents empty; run only separately approved inventory/supplier seeds.

Prefer a forward-fix. Use PITR or dump restore only with separate approval and
documented downtime/RPO impact.
