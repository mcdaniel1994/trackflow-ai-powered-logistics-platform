# Supabase Migrations and Recovery

## Status

The two-role bootstrap was verified on July 2, 2026 against the portfolio
Supabase Free project in `us-east-2` through Supavisor Session mode on port
`5432`. Both roles authenticated over TLS, and the migration role's future
table and sequence grants were verified.

The first production migration was separately approved and completed on July
3, 2026 UTC through Alembic revision `20260702_0003`. The runtime role's CRUD
access was verified across all six tables. After separate approval, inventory
and 15 suppliers were seeded; production incidents remained empty.

## Safety boundary

Do not execute this runbook against production without explicit approval that
names the target and confirms either a backup or the disposable-data waiver,
then accepts the recovery path.

For the current Supabase Free portfolio deployment, the owner accepts no
managed backup and disposable data. Before later risky migrations on meaningful
data, take an off-site logical dump or stop and revisit this waiver.

Never place database passwords or complete connection strings in this file,
source control, screenshots, chat, command history, or application logs.

## Why TrackFlow uses two database roles

TrackFlow separates normal application traffic from schema administration:

| Role | Used by | Allowed | Intentionally denied |
|---|---|---|---|
| `trackflow_runtime` | Central API and seed commands through `DATABASE_URL` | Connect; use `public`; select, insert, update, and delete application rows; use sequences | Creating or altering schemas/tables, creating roles/databases, superuser access |
| `trackflow_migration` | Explicit Alembic setup job through `MIGRATION_DATABASE_URL` | Connect; use and create objects in `public`; apply reviewed schema migrations | Superuser access, creating roles/databases, routine application traffic |

The Supabase `postgres` account is administrative and is never given to the
running application. If the Central API were compromised, its runtime
credential could affect application data, but it could not create roles,
create databases, or use the migration identity to change the schema. The
migration credential is exposed only to the inactive, explicit
`central-api-migrate` setup service.

This boundary also makes operations easier to audit: ordinary queries identify
as `trackflow_runtime`, while schema changes identify as
`trackflow_migration`. It implements the repository database standard's
least-privilege requirement without exposing Supabase directly to the browser.

## Verified role bootstrap

### 1. Create the roles as the Supabase administrative user

Generate two different long random passwords in a password manager. In the
Supabase SQL Editor, which reports `current_user = postgres`, replace the
placeholders and run:

```sql
BEGIN;

CREATE ROLE trackflow_runtime LOGIN PASSWORD '<runtime-secret>';
CREATE ROLE trackflow_migration LOGIN PASSWORD '<migration-secret>';

GRANT CONNECT ON DATABASE postgres TO trackflow_runtime, trackflow_migration;
GRANT USAGE, CREATE ON SCHEMA public TO trackflow_migration;
GRANT USAGE ON SCHEMA public TO trackflow_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO trackflow_runtime;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO trackflow_runtime;

COMMIT;
```

Verify that both roles can log in and are not superusers and cannot create
databases or roles:

```sql
SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname IN ('trackflow_runtime', 'trackflow_migration');
```

### 2. Set future grants while connected as the migration role

Supabase's SQL Editor rejected `ALTER DEFAULT PRIVILEGES FOR ROLE
trackflow_migration` from the `postgres` session with PostgreSQL error `42501`.
Default privileges belong to the role that will create the future objects, so
connect as `trackflow_migration` and alter its own defaults instead.

The current portfolio project's Session-mode connection shape is:

```text
host=aws-1-us-east-2.pooler.supabase.com
port=5432
dbname=postgres
user=trackflow_migration.ajdmajuecqelwxbiajiz
sslmode=require
```

Use a client that prompts for the password rather than putting it in shell
history. One verified option is:

```bash
docker run --rm -it postgres:17-alpine psql \
  "host=aws-1-us-east-2.pooler.supabase.com port=5432 dbname=postgres user=trackflow_migration.ajdmajuecqelwxbiajiz sslmode=require"
```

After confirming that both `current_user` and `session_user` are
`trackflow_migration`, run:

```sql
BEGIN;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trackflow_runtime;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT USAGE ON SEQUENCES TO trackflow_runtime;

COMMIT;
```

Query `pg_default_acl` or run `\ddp`. The expected migration-owned entries are:

```text
trackflow_runtime=arwd/trackflow_migration  # table: insert, select, update, delete
trackflow_runtime=U/trackflow_migration     # sequence: usage
```

Finally, connect once as `trackflow_runtime` through the same Session pooler
and verify `SELECT current_user, session_user;` plus `SELECT 1;`.

## Coolify connection variables

Store these only as secret environment variables in Coolify. Passwords
containing URL-reserved characters must be percent-encoded.

```text
DATABASE_URL=postgresql://trackflow_runtime.ajdmajuecqelwxbiajiz:<runtime-secret>@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require
MIGRATION_DATABASE_URL=postgresql://trackflow_migration.ajdmajuecqelwxbiajiz:<migration-secret>@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require
```

Never substitute the `postgres.<project-ref>` administrative connection for
either variable. Use Session mode `:5432`, not transaction mode `:6543`.

## Migration procedure

1. Confirm project ref, region, role, current Alembic revision, and approved
   maintenance window.
2. Confirm a verified backup or the explicitly accepted disposable-data
   waiver. For meaningful data, create an encrypted off-site `pg_dump` and
   verify it can be read.
3. Test `alembic upgrade head` against a disposable restored copy.
4. Run the explicit `central-api-migrate` one-off.
5. Verify Alembic head, constraints, runtime-role CRUD, and Central API health.
6. Keep incidents empty; run only separately approved inventory/supplier seeds.

Prefer a forward-fix. Use PITR or dump restore only with separate approval and
documented downtime/RPO impact.
