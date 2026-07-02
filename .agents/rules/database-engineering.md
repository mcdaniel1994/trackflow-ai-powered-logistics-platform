# Database Engineering

## Rule Name

Database Engineering

## Scope

File-pattern and task based.

## Applies When

Planning, reviewing, or changing database-backed persistence, including:

- database or ORM selection;
- database configuration, repositories, persistence models, SQL, or query builders;
- schemas, keys, constraints, relationships, indexes, or data types;
- transactions, concurrency, idempotency, or data isolation;
- migrations, data transformations, seeds, backup, restore, or retention;
- database performance or execution against production or non-disposable shared data.

This includes relational, document, embedded, and file-backed stores such as TinyDB.

## Required Behavior

- Before planning or implementing, read
  [`docs/standards/database-engineering-standard.md`](../../docs/standards/database-engineering-standard.md).
- Infer the engine, persistence layer, deployment context, tenancy, and data sensitivity from the
  repository and active brief before asking questions.
- Apply the related testing, error-handling, observability, authentication, and
  production-readiness standards when their scopes also match.
- Do not execute high-risk actions against production or non-disposable shared data without the
  explicit approval required by the database standard.
- Treat the standard, not this routing rule, as the source of database guidance.

## Examples

- Adding a SQLModel model, constraint, index, migration, repository, or seed.
- Changing a TinyDB collection or repository write strategy.
- Designing the Engagement 5 inventory database.
- Reviewing transaction safety or tenant isolation.
- Running a production data repair, migration, restore, or retention operation.

## Non-Examples

- Changing a UI that only consumes an existing API contract.
- Editing a response-only schema with no persistence effect.
- Copy or documentation edits that merely mention a database without prescribing database behavior.
