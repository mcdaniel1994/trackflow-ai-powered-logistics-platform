# `services/`

Home for TrackFlow APIs and backend services.

Do not place UI code or shared library code here.

## Service boundaries

The `services/` root is organizational; it is not a shared runnable application.
Each subfolder is an independently deployable service with its own:

- business and persistence ownership;
- dependencies and runtime configuration;
- tests and release gates;
- deployment lifecycle; and
- failure boundary.

Services communicate through explicit API or signed-token contracts. They do not reach
into another service's private persistence. In particular, Central API verifies signed
Identity access tokens through `packages/trackflow_auth`; it never opens Identity's
TinyDB file.

Current deployable peers:

- `services/identity/` - FastAPI + TinyDB identity service for Auth 1 backend authentication and API route protection. It is not Engagement 5.
- `services/incident-processor/` - FastAPI service for the Incident Report Processor subproject. It is not Engagement 5.
- `services/supplier-directory/` - FastAPI + TinyDB service for the Supplier Directory subproject. It is not Engagement 5.
- `services/central-api/` - Engagement 5 FastAPI modular monolith for closely related
  core logistics domains, beginning with PostgreSQL-backed inventory.

The Central API is a modular monolith inside its own deployable boundary, not a merger
of the peer services above. New closely related logistics domains may later join its
domain-oriented structure when an engagement explicitly scopes them.

Python services are independent `uv` projects, not npm workspaces. Use each service's
`pyproject.toml`, lockfile, README commands, and environment configuration.
