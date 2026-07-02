# Database Engineering Standard

**Last reviewed:** July 2026  
**Next review due:** October 2026 (quarterly)

## Scope

Applies to database and persistent-storage design, implementation, review, migration, security,
performance, recovery, and production operation.

It covers relational, document, embedded, managed, and file-backed stores. Requirements must be
interpreted according to the capabilities and deployment context of the selected store.

For overlapping concerns, also follow:

- [Testing Standards](testing.md)
- [Error Handling Standards](error-handling.md)
- [Observability Standards](observability.md)
- [Production-Readiness Standards](production-readiness.md)
- [Authentication & Session Security Standard](authentication-security-standard.md) when identity or
  authorization data is involved

Those standards remain authoritative for their respective topics.

## How to Use This Standard

1. **Infer before asking.** Determine the current engine, query layer, deployment model, tenancy,
   data sensitivity, and relevant brief from the repository.
2. **Scale rigor to risk.** Production and non-disposable shared data require stronger operational
   controls than local, test, or disposable data.
3. **Preserve established decisions.** Do not replace an existing engine, persistence boundary, or
   active-brief requirement without explicit scope.
4. **Plan freely; gate high-risk execution.** Design and code may be prepared without production
   access. High-risk execution requires approval as defined below.

## New Database Discovery

For a new database, resolve only the questions the repository does not answer:

1. What data is stored, and what is the impact of loss, corruption, or exposure?
2. What tenancy or customer-isolation boundary applies?
3. What read/write patterns and transactional guarantees are required?
4. Where will it run, who operates it, and what near-term scale is expected?
5. What recovery point and recovery time are required for production?

For a smaller change to an existing database, preserve existing decisions and ask only questions
that materially affect that change.

## Baseline Requirements

- Classify data sensitivity before deciding how it is stored or exposed.
- Use database-enforced keys, constraints, and specific types where supported. When the store lacks
  those capabilities, enforce invariants in the repository or service layer, test them, and
  document the limitation.
- Use parameterized SQL or the query API supplied by the selected library. Never concatenate
  untrusted input into executable queries.
- Treat connection strings and credentials as secrets. Keep them out of source, logs, client
  bundles, and committed configuration.
- Deployed applications use least-privilege database access. Use separate application, migration,
  and administrative identities where supported and operationally practical.
- Require encrypted connections for remote production databases. Embedded and isolated
  local-development stores are not network TLS connections.
- Store timestamps in UTC. Prefer a timezone-aware native type; otherwise use one documented
  canonical UTC representation.
- Use versioned migrations for schema-capable databases. For schema-less stores, use versioned,
  repeatable data transformations or compatibility handling.
- Multi-step writes that must succeed or fail together use a transaction when supported. If
  transactions are unavailable, document and test the coordination, idempotency, compensation, or
  single-writer strategy.
- Seeds and backfills are repeatable or explicitly one-time, bounded, and safe to retry.
- Production and non-disposable shared data require a documented recovery path. Production systems
  must define RPO/RTO and periodically verify restoration. Disposable local and test databases may
  be recreated instead.

## Context-Dependent Decisions

- **Engine:** Choose from workload, consistency, deployment, operational capacity, and active-brief
  requirements. Do not introduce another store merely from habit.
- **ORM or query layer:** Raw SQL, query builders, and ORMs are acceptable. Preserve explicit
  migrations and watch for hidden N+1 or unbounded queries.
- **Schema:** Normalize transactional data by default. Denormalize deliberately for a demonstrated
  read need and document the consistency strategy.
- **Tenancy:** Enforce tenant scope in every data access path. Add row-level security or stronger
  physical isolation when risk warrants and the engine supports it.
- **Consistency:** Money, inventory, and authoritative state transitions require atomic, strongly
  consistent writes. Eventual consistency is suitable only for explicitly derived data.
- **Indexes:** Derive indexes from real query and constraint needs. Verify query plans for important
  or degraded paths.
- **Connections:** Use pooling and connection, statement, and lock timeouts when applicable to the
  engine and runtime. Embedded stores may require a different concurrency strategy.
- **Migration recovery:** Prefer backward-compatible migrations and expand/contract deployment. Use
  rollback, forward-fix, or restore according to what has been tested and is safest.

## Unsafe Practices

- Selecting an engine or ORM before understanding the existing repository and workload.
- Storing structured transactional data as opaque JSON merely to avoid schema design.
- Relying only on application validation when the database can enforce integrity.
- Concatenating untrusted input into queries.
- Using administrative credentials for the running application.
- Hand-editing production schema or data outside a reviewed procedure.
- Executing destructive or table-rewriting migrations without impact analysis and a verified
  recovery path.
- Unbounded reads, updates, or deletes on potentially large data sets.
- Storing local-time timestamps without an unambiguous timezone.
- Trusting an unverified backup.
- Premature sharding or distributed-database adoption.
- Logging credentials, connection strings, queries containing sensitive values, or full sensitive
  records.

## Approval Required Before Execution

Get explicit approval before executing the following against production or a non-disposable shared
environment:

- Drop, truncate, lossy type conversion, irreversible rewrite, or large-scale
  deletion/anonymization.
- An unbounded or high-volume update/backfill with material lock, load, or data-correctness risk.
- A migration expected to cause downtime, rewrite a large table, break backward compatibility, or
  be difficult to reverse.
- A restore, failover, cutover, or replacement of authoritative data.
- Widening database network exposure, granting privileged access, disabling encryption, or reducing
  backup/retention protections.
- Any operation with a comparable, material, hard-to-reverse blast radius.

When requesting approval, state the target environment, expected impact, backup or snapshot status,
verification plan, and recovery path.

A separate approval is not required merely because a migration is additive and runs in production
when it is backward-compatible, tested, reversible or safely forward-fixable, and already covered
by an approved deployment procedure. If no verified production procedure exists, do not improvise
one.

## TrackFlow-Specific Application

- Existing TinyDB services are documented transitional implementations. Do not pretend they provide
  SQL constraints, transactions, indexes, pooling, TLS, or schema migrations.
- Preserve TinyDB authentication unless an active brief explicitly authorizes its migration.
- For TinyDB changes, keep persistence behind repository interfaces, use stable identifiers and
  canonical UTC timestamps, coordinate writes, and test the invariants the store cannot enforce.
- New inventory writes that prevent negative stock must check availability and record the movement
  atomically. A separate read followed by an unlocked write is insufficient.
- References from SQL data to TinyDB users are external identifiers, not database foreign keys.
  Validate them at the service boundary and document the resulting referential-integrity
  limitation.
- Do not claim production readiness while backup, restore, deployment, or recovery procedures
  remain unverified.

## Testing

Follow [Testing Standards](testing.md); select tests based on the behavior changed.

As applicable, verify:

- changed constraints or repository invariants;
- transaction rollback, concurrency behavior, and idempotent retry;
- tenant or warehouse isolation;
- injection-safe query handling;
- migrations against representative data and their recovery strategy;
- bounded backfills and seed repeatability;
- backup restoration as an operational production-readiness gate.

## Review Checklist

- [ ] Existing engine, brief, tenancy, sensitivity, and deployment context confirmed.
- [ ] Integrity is enforced at the strongest supported layer.
- [ ] Queries are injection-safe and appropriately bounded.
- [ ] Credentials are secret and deployed access is least-privilege.
- [ ] Atomicity, concurrency, and idempotency match the business risk.
- [ ] Versioned migration or transformation path exists.
- [ ] Recovery requirements match the environment and data durability.
- [ ] High-risk production execution is approval-gated.
- [ ] Applicable tests and related TrackFlow standards are satisfied.

## Sources to Consult

Use current official documentation for the selected database engine and version.

Primary references:

- PostgreSQL Official Documentation
- OWASP Database Security Cheat Sheet
- OWASP SQL Injection Prevention Cheat Sheet
- OWASP Secrets Management Cheat Sheet
- OWASP Cryptographic Storage Cheat Sheet
- OWASP Key Management Cheat Sheet
- OWASP NoSQL Security Cheat Sheet
- NIST SP 800-53 Rev. 5
- NIST SP 800-53A Rev. 5
- NIST SP 800-92
- NIST SP 800-209
- HHS HIPAA Security Rule guidance
- PCI Security Standards Council — PCI DSS
- Official GDPR text and regulator guidance
- California Attorney General CCPA guidance

Engine-specific behavior, commands, security features, migration behavior, backup tooling, and operational limits must be verified against the current official documentation for the exact database version in use.
