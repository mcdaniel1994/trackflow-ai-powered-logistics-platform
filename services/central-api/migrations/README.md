# Central API migrations

Alembic owns every shared schema change. Application startup never calls
`SQLModel.metadata.create_all()`. Phase 3 adds the migration environment and initial
inventory revision, which are verified against the disposable PostgreSQL service in
`../compose.yml`.

The current additive head is `20260818_0018`, which adds owner-scoped Engagement 10
`chat_sessions` and `chat_messages`. Production migration execution remains part of the normal
approval-gated deployment path; Phase 3 verification uses only the disposable local PostgreSQL.
