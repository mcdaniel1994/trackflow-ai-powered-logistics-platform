# Backend Architecture Planning Brief

## Purpose

TrackFlow has completed its fourth major delivery: the corporate site, AI-assisted engineering infrastructure, persistent project memory, shared repository rules, and forward-looking UI workspace are now in place.

The next major build direction is the backend. Before the team begins creating environments, endpoints, services, or database connections, we need a shared architecture plan for how the backend should be structured.

This planning brief prepares the ground for that architecture proposal. It is not the official Engagement 5 brief. Instead, it is an internal planning document meant to guide the creation of the backend architecture proposal before implementation begins.

This file should set up Claude Code to scan the repository fully and then create the CTO-facing proposal at `docs/planning/architecture-api.md`. This file is not the final proposal.

---

## Background

TrackFlow is a logistics operator serving e-commerce brands across the United States and Spain. The company runs warehouse and last-mile delivery operations from Los Angeles and Zaragoza.

The platform is being built as a long-term engineering system, not as a collection of isolated demos. Each completed engagement has added another part of the operational foundation:

- A public-facing corporate website and lead capture flow
- Shared inventory and carrier scoring logic
- A talent pipeline tracker
- AI-driven engineering infrastructure, including project memory, agent rules, and forward-looking UI boundaries

The repository now includes clear areas for applications, shared packages, UI workspaces, documentation, data, agents, workflows, and future backend services.

The next step is to define how the backend should be organized before the team begins writing backend code.

---

## Claude Code Handoff

Claude Code should use this planning brief as a starting point, then scan the repository before drafting the final architecture proposal.

At minimum, Claude Code should review:

- `memory-bank/`
- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `docs/briefs/`
- `packages/shared/`
- `uis/`
- `services/`

Claude Code should reconcile the FastAPI direction in this brief with the existing repository context, especially the reserved `services/` boundary and any README or orientation-file language about future backend services.

The final CTO-facing architecture proposal should be created at:

```text
docs/planning/architecture-api.md
```

After that proposal exists, this file becomes a preparatory/archive input for the planning process. Do not move this file into `docs/archive/` unless a later task explicitly asks for that move.

---

## Planning Challenge

TrackFlow needs a backend architecture proposal before implementation begins.

The engineering team should not start building endpoints, services, or data models without first agreeing on the structure of the backend. The architecture proposal should explain the reasoning behind the backend design, not simply list technologies.

The proposal should answer questions such as:

- What architectural pattern should TrackFlow use for the backend?
- Why does that pattern fit this company and this platform?
- How should backend folders, modules, and domains be organized?
- How should FastAPI endpoints and routers be grouped?
- How should the backend communicate with the separate frontend systems?
- What risks should the team avoid as the backend grows?

The goal is to create a document that gives any engineer or AI coding agent enough context to understand the intended backend structure before starting implementation.

This planning task is not the actual next `milestone-05` itself. It should not change the entire repo structure, create a new milestone brief, scaffold a backend service, install FastAPI, create endpoints, or update engagement-tracking documents.

---

## Internal CTO Request

Before the team starts setting up the backend environment and first endpoints, we need a clear architecture document that explains how the backend should be structured.

No code is needed yet.

The document should explain:

- The proposed architectural pattern
- Why that pattern fits TrackFlow
- How the backend modules and domains should be organized
- What initial technical decisions should guide the backend
- How FastAPI project conventions influence the structure
- How the backend should coexist with the existing frontend systems
- Where the team may run into confusion or architectural risk

The proposal should be based on what we already know about TrackFlow’s operations, users, data, and business-critical workflows.

TrackFlow’s backend will need to support logistics operations, shared inventory visibility, carrier performance logic, returns workflows, customer support automation, CRM-like account management, reporting, and future AI/data integrations. The architecture should reflect those realities.

---

## What Makes a Strong Architecture Proposal

A strong architecture proposal is documented technical reasoning.

It should explain:

- **What** structure is being proposed
- **Why** that structure fits the system
- **How** the backend should be organized
- **What consequences** the team should expect from the decision
- **What risks** could appear if the structure is not followed

The document should allow another engineer, technical lead, or AI coding agent to understand the decision without needing additional verbal explanation.

At minimum, the proposal should cover:

- The chosen architectural pattern and justification
- The proposed folder and module structure
- Route and domain organization
- FastAPI structure conventions
- Frontend/backend separation concerns
- Risks and points of attention

---

## Repository Location

This planning work should live inside the existing TrackFlow monorepo.

Create a new planning folder inside `docs`:

```text
docs/planning/
```

Then create the planning document for this backend architecture work inside that folder.

Recommended file name:

```text
docs/planning/backend-architecture-planning.md
```

This file should not be placed in `docs/briefs/` because it is not the official Engagement 5 brief. It is a planning document that will support the later architecture proposal.

## Work To Be Completed

Create a Markdown planning document that prepares the team to write the backend architecture proposal.

The final architecture proposal should include the following:

## 1. Architectural Pattern

Identify and justify the most suitable backend architectural pattern for TrackFlow.

Possible patterns to consider include:

- MVC
- Layered architecture
- Domain-oriented layered architecture
- Serverless
- Another justified backend structure

The chosen pattern should be tied directly to TrackFlow’s actual needs, not chosen because it is generally popular.

The justification should consider TrackFlow’s real operating context:

- Multiple warehouses
- Inventory visibility problems
- Carrier scoring and carrier performance data
- Returns workflows
- Customer support needs
- CRM/account management gaps
- Manual reporting
- Future AI agents and data pipelines

## 2. Backend Folder and Module Structure

Propose how the backend project should be organized.

The structure should explain:

- Where the backend should live in the monorepo
- How backend modules should be separated
- Which folders represent technical layers
- Which folders represent business domains
- How the structure prevents the backend from becoming one large file or unclear service

The proposed structure should fit the existing TrackFlow repository boundaries, especially the reserved `services/` area.

## 3. Domain Organization

Identify the main backend domains that TrackFlow will likely need.

Potential domains include:

- Warehouses
- Inventory
- Orders
- Carriers
- Returns
- Customers
- Support
- Reports
- Authentication/authorization
- AI or automation interfaces

The proposal should explain why these domains should be separated and how they connect to TrackFlow’s operational workflows.

## 4. FastAPI Router and Endpoint Organization

Describe how FastAPI endpoints and routers should be organized.

No code is required.

The document should explain:

- How routers should be grouped
- Why routes should be grouped by domain
- Why all endpoints should not live in one file
- How route prefixes should be handled
- How API versioning should be considered

Example route groupings may include:

- `/api/v1/inventory`
- `/api/v1/carriers`
- `/api/v1/returns`
- `/api/v1/customers`
- `/api/v1/support`
- `/api/v1/reports`

The goal is to create a structure that would be recognizable as a valid FastAPI backend design.

## 5. FastAPI Project Structure Research

Research how FastAPI projects are typically structured.

The proposal should reflect standard FastAPI conventions such as:

- `main.py` as the application entry point
- `APIRouter` for separating route groups
- Separate modules for routers/endpoints
- Separate schemas for request and response models
- Configuration management
- Dependency handling
- Separation between API routes and business logic

The proposal should briefly mention how FastAPI’s standard structure influenced the TrackFlow backend design.

## 6. Frontend and Backend Separation

TrackFlow already has frontend-facing areas in the repository, including public website and backoffice UI workspaces.

The architecture proposal should explain how frontend and backend systems should coexist as separate systems.

The document should address:

- How frontend applications communicate with the backend API
- Why the frontend should not directly access the database
- How API base URLs should be configured
- How environment variables should be managed
- How CORS should be handled
- How local development and production environments may differ

At minimum, the proposal should explain the implications of:

```text
Frontend UI → HTTP API request → FastAPI backend → database/services
```

## 7. Risks and Points of Attention

Include a section describing what could go wrong if the team does not follow the proposed backend structure.

At least two risks should be clearly explained.

Possible risks include:

- Putting all routes in one file
- Mixing business logic directly into route handlers
- Weak frontend/backend contracts
- Poor environment variable management
- Incorrect CORS configuration
- Confusing domain boundaries
- Ignoring the existing monorepo structure
- Creating backend code that future AI agents cannot easily understand or maintain

Each risk should explain both the problem and why it matters for TrackFlow.

## Evaluation Standard

The architecture proposal should be evaluated by the quality of its technical reasoning.

A strong proposal should show that:

- The chosen architecture pattern fits TrackFlow’s business and system needs
- The folder structure is consistent with the chosen pattern
- Responsibilities are clearly separated
- FastAPI router organization is clear and domain-based
- The proposal reflects real FastAPI project conventions
- Frontend/backend separation is understood
- CORS and environment variable concerns are addressed
- Risks are concrete and connected to the actual project
- The document gives enough guidance for a coding agent or engineer to begin planning implementation

This is not an implementation task. FastAPI does not need to be installed, and no working backend code is required at this stage.

## Expected Deliverable

The expected deliverable from this planning document is a CTO-facing Markdown proposal that Claude Code can create after reviewing this file and scanning the repository.

Recommended file path:

```text
docs/planning/architecture-api.md
```

That proposal should describe the actual backend architecture plan for TrackFlow’s Central API.

## Next Step After This Planning Document

After this planning document is added to the repository, Claude Code can review it, scan the repository, and use both sources of context to create `docs/planning/architecture-api.md`.

For now, this document should remain in `docs/planning/` because it is preparatory planning, not the official engagement brief and not the final CTO-facing architecture proposal.
