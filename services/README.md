# `services/`

Reserved for TrackFlow APIs and backend services.

Do not place UI code or shared library code here.

Subfolders correspond to discrete services:

- `services/identity/` - FastAPI + TinyDB identity service for Auth 1 backend authentication and API route protection. It is not Engagement 5.
- `services/incident-processor/` - FastAPI service for the Incident Report Processor subproject. It is not Engagement 5.
- `services/supplier-directory/` - FastAPI + TinyDB service for the Supplier Directory subproject. It is not Engagement 5.
- `services/central-api/` - reserved name for the future Central API engagement.

Python services are managed independently from npm workspaces. Use the service-level `pyproject.toml` and `uv` commands documented in each service README.
