# Brief: AI-Driven Engineering Infrastructure

## Client: TrackFlow · Stakeholder: Andrés Kim (CTO)

## Status

✅ Delivered — Engagement 4 infrastructure lives in `memory-bank/`, `AGENTS.md`, `.agents/`, `uis/website/`, `uis/backoffice/`, and `services/`.

---

## Background

TrackFlow has completed three foundational engagements: the public marketing website, the shared TypeScript logistics logic, and the Talent Pipeline Tracker for internal recruiting operations.

Those milestones delivered useful pieces, but the repository is now reaching a new phase. From this engagement forward, TrackFlow's monorepo must become the durable technical core of the company: the place where future user interfaces, APIs, AI agents, automations, data pipelines, and dashboards can grow without losing context or consistency.

Before adding more product features, the repository needs stronger engineering infrastructure. Coding agents must understand the company, the architecture, the completed milestones, and the rules for making changes. The repo also needs a clearer UI structure so future frontend work does not collide with past deliverables.

## Stakeholder Request

Andrés Kim, CTO, has raised the following request:

> We are accumulating code without enough supporting structure. If I ask a coding agent to work in this repository as it stands, it may miss business context, misunderstand technical boundaries, and make changes that cost us more time to fix later.
>
> I need the repository to have persistent context before we keep adding features. The agent must know what TrackFlow is, what we are building, which architectural decisions have already been made, and what constraints it must respect.
>
> I also want a root `AGENTS.md` that defines how any coding agent operates in this repo before making changes or commits. More specific conventions should live under `.agents/`, with clear scope.
>
> Finally, I want us to formalize at least one reusable skill for a recurring workflow. It must have a single objective and verifiable acceptance criteria.
>
> For the application structure, the public website should move forward as a Next.js + TypeScript app in `./uis/website`, using reusable components rather than a static copy. In parallel, create `./uis/backoffice` as the home for internal company tools, with an initial view that integrates the TypeScript business logic from Engagement 2. Any future APIs must be created under `/services`.
>
> When this is done, open a PR.
>
> - Andrés Kim, CTO

## Assignment

Build the engineering foundation that allows TrackFlow's monorepo to be maintained by both humans and AI coding agents without losing project context, breaking established milestones, or creating ambiguous architecture.

This engagement is not just about adding folders. The new infrastructure must reflect TrackFlow's real business, current repository structure, delivered engagements, technical constraints, and roadmap.

## What You're Building

### 1. Memory Bank

Create a root-level `memory-bank/` folder containing persistent project context for coding agents.

Required files:

- `projectbrief.md`
  - TrackFlow business description
  - Project objectives
  - Operational problems the platform is solving
  - Key stakeholders and departments

- `techContext.md`
  - Current tech stack
  - Repository architecture
  - Delivered engagements
  - Architectural decisions and constraints
  - Where future apps, services, agents, workflows, and data assets belong

- `progress.md`
  - Current state of development
  - Completed engagements
  - Active engagement
  - Planned next steps
  - Open decisions or known risks

The memory bank must be TrackFlow-specific. Generic project boilerplate is not acceptable.

### 2. Agent Operating Guide

Create a root-level `AGENTS.md` file that defines how coding agents must work in this repository.

It must include:

- Which memory bank files the agent must read at the start of every session
- Which engagement brief must be read before implementation
- A mandatory pre-commit workflow with at least four ordered steps
- Folders and files that must not be modified without explicit developer confirmation
- Guidance for preserving delivered milestone work
- Guidance for respecting repository boundaries

### 3. Scoped Agent Rules

Create a root-level `.agents/` folder for coding-agent configuration.

Minimum structure:

```txt
.agents/
  rules/
    <rule-name>.md
  skills/
    <skill-name>/
      SKILL.md
```

At least one development rule must be documented.

Each rule must include:

- Rule name
- Scope
- When it applies
- Required behavior
- Examples or non-examples where useful

Allowed scopes:

- Always active
- File-pattern based
- Agent-requested

### 4. Reusable Agent Skill

Create at least one reusable coding-agent skill under `.agents/skills/`.

The skill must include:

- A single clear objective
- Required inputs
- Step-by-step workflow
- Expected output
- Explicit acceptance criteria
- Verification method

The skill should capture a recurring TrackFlow workflow, such as preparing a new engagement, updating memory bank context, or reviewing milestone readiness.

### 5. UI Workspace

Introduce a root-level `uis/` workspace for Engagement 4 frontend work.

Required projects:

- `uis/website`
  - Next.js + TypeScript public website
  - Migrates and improves the Engagement 1 corporate website
  - Uses reusable components
  - Preserves the major sections and lead-capture intent from the original static site
  - Follows TrackFlow's public visibility and discoverability standards

- `uis/backoffice`
  - Next.js + TypeScript internal backoffice app
  - Provides a shared layout and entry view for internal TrackFlow tools
  - Includes visible functionality powered by the Engagement 2 TypeScript business logic in `packages/shared`

### 6. Repository Clarity

Rename the existing Engagement 3 app from:

```txt
apps/uis
```

to:

```txt
apps/talent-pipeline-tracker
```

This avoids ambiguity between the old app folder and the new root-level `uis/` workspace.

After the rename:

- `apps/marketing-site` remains the delivered Engagement 1 static website
- `apps/talent-pipeline-tracker` becomes the delivered Engagement 3 recruiting app
- `uis/website` becomes the new Engagement 4 public website app
- `uis/backoffice` becomes the new Engagement 4 internal UI app

The `apps/` folder is not removed in this engagement. It remains a home for delivered historical apps unless a future migration decision explicitly changes that.

### 7. Services Boundary

Create or reserve a root-level `services/` folder as the location for future APIs and backend services.

No full production API is required in this engagement unless a later implementation plan explicitly adds one. The purpose is to establish the architectural boundary now.

## Important Distinction

Do not confuse these folders:

- `.agents/`
  - Configuration for coding agents working in this repository

- `agents/`
  - Product AI agents built for TrackFlow in later engagements

- `.agents/skills/`
  - Reusable workflows for coding agents

- `skills/`
  - Product or AI capabilities used by TrackFlow agents in later engagements

These are different architectural concerns and must remain separate.

## Acceptance Criteria

The engagement is complete when:

- `memory-bank/` exists with `projectbrief.md`, `techContext.md`, and `progress.md`
- Memory bank content accurately reflects TrackFlow's business, completed engagements, and roadmap
- Root `AGENTS.md` defines startup reading requirements and a mandatory pre-commit workflow
- `.agents/` exists with at least one scoped development rule
- `.agents/skills/` contains at least one reusable skill with verifiable acceptance criteria
- Existing `apps/uis` has been renamed to `apps/talent-pipeline-tracker`
- Documentation references to the Talent Pipeline Tracker use the new path
- `uis/website` exists as a Next.js + TypeScript app
- `uis/website` includes an improved component-based version of the corporate website
- `uis/backoffice` exists as a Next.js + TypeScript app
- `uis/backoffice` includes an initial internal view using Engagement 2 business logic
- `/services` exists or is clearly reserved for future APIs
- Existing Engagement 1, 2, and 3 deliverables remain intact unless an explicit migration decision is documented
- Documentation clearly explains the difference between `.agents/`, `agents/`, `.agents/skills/`, and `skills/`
- A pull request is opened when implementation is complete

## Out of Scope

- Building production AI agents
- Building RAG or semantic search
- Creating n8n automations
- Building the full central API
- Replacing the Talent Pipeline Tracker
- Migrating all historical apps into the new `uis/` workspace
- Removing the `apps/` folder
