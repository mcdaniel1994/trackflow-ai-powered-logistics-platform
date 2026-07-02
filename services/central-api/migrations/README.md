# Central API migrations

Alembic owns every shared schema change. Application startup never calls
`SQLModel.metadata.create_all()`. Phase 3 adds the migration environment and initial
inventory revision, which are verified against the disposable PostgreSQL service in
`../compose.yml`.
