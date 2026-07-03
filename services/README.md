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
- `services/supplier-directory/` - legacy TinyDB rollback copy retained only
  through the PostgreSQL supplier cutover observation window.
- `services/central-api/` - Engagement 5 FastAPI modular monolith for closely related
  core logistics domains: PostgreSQL-backed inventory, incidents, and suppliers.

The Supplier Directory migration brief explicitly waives the default service
boundary for suppliers. Identity remains separate and Central API never opens
its TinyDB.

Python services are independent `uv` projects, not npm workspaces. Use each service's
`pyproject.toml`, lockfile, README commands, and environment configuration.
