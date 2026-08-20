# Central API migrations

Alembic owns every shared schema change. Application startup never calls
`SQLModel.metadata.create_all()`. Phase 3 adds the migration environment and initial
inventory revision, which are verified against the disposable PostgreSQL service in
`../compose.yml`.

The `codex/async-tasks-dev55` coursework branch has local-only additive head `20260820_0019`, which
adds terminal Celery failure evidence and the RFP `failed` status. It is explicitly not approved for
production or merge. The `main`/production line remains `20260818_0018`, which adds owner-scoped
Engagement 10 `chat_sessions` and `chat_messages`; its production migration and rollout remain
deferred. Migration verification for DEV-55 uses only disposable local PostgreSQL.
