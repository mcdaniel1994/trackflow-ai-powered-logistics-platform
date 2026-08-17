# Remaining Planning

This folder is the **entry point for all remaining TrackFlow work**. When a session begins with
"we're working on <project>", start here, find that project below, and follow its reading order.

It holds two different kinds of document, and confusing them is the main failure mode this README
exists to prevent.

---

## 1. Precedence — read this before anything else

| Kind | Examples | Authority |
|---|---|---|
| **Approved specification** | `spec.md`, `spec-6.5-sales-forecasting.md`, `docs/agents/agent-design.md` | **Binding.** Owner-approved. Implement what it says. |
| **Planning input** | `07_rag_knowledge_base/`, `08_agent_engineering/`, `09_agentic_workflows/`, `10_realtime/`, `sales_forcasting/`, `important_considerations/` | **Requirements and constraints, not architecture.** |

**Planning inputs are bootcamp assignment material.** They describe what must be delivered and what
will be graded. They were not written against this repository, and they may conflict with the
current codebase, with the production deployment, or with each other. Treat their **requirements**
as constraints and their **suggested architecture** as one option among several.

Resolution order when documents disagree:

1. An approved specification listed in this index wins over any planning input.
2. `AGENTS.md`, `docs/standards/`, and the production reality of the deployed system win over a
   planning input's assumed architecture.
3. If a planning input's *graded requirement* conflicts with repository architecture, **surface the
   conflict to the owner** — do not silently satisfy one and drop the other.

**If a project below has no approved specification, do not implement it.** Produce analysis and a
proposed spec first, and stop for owner approval. That is how `spec.md` and
`spec-6.5-sales-forecasting.md` came to exist.

---

## 2. Index

| Project | Folder / file | Spec | Status |
|---|---|---|---|
| **Engagement 6.1–6.4** — reporting reliability | [`spec.md`](spec.md) | ✅ approved | Ready to implement |
| **Engagement 6.5** — sales forecasting | [`spec-6.5-sales-forecasting.md`](spec-6.5-sales-forecasting.md), [`sales_forcasting/`](sales_forcasting/) | ✅ approved | Ready to implement, **parallel to 6.1–6.4** |
| **Engagement 7** — RAG knowledge base | [`07_rag_knowledge_base/`](07_rag_knowledge_base/) | ❌ none | Needs analysis + spec |
| **Engagement 8** — agent engineering | [`08_agent_engineering/`](08_agent_engineering/), [`docs/agents/agent-design.md`](../../agents/agent-design.md) | ✅ approved | ✅ Complete — owner accepted August 3, 2026 |
| **Engagement 9** — agentic workflows (RFP desk) | [`09_agentic_workflows/`](09_agentic_workflows/) | ✅ delivered | Complete — merged to `main` and deployed to production (2026-08-17) |
| **Engagement 10** — real-time dashboards and alerts | [`10_realtime/`](10_realtime/) | ❌ none | ⛔ **Blocked — no requirements exist** |
| **Cross-cutting backlog** | [`important_considerations/others.md`](important_considerations/others.md) | ❌ none | Unscheduled; fold into the engagement that needs it |

---

## 3. Sequence

1. **Engagement 6.1–6.4** — reporting reliability *(availability-critical; do this first)*
2. **Engagement 6.5** — sales forecasting *(independent; runs in parallel, not after)*
3. **Engagement 7** — RAG and knowledge base
4. **Engagement 8** — agent engineering *(complete; retained here for dependency history)*
5. **Engagement 9** — agentic workflows
6. **Engagement 10** — real-time dashboards and alerts

Engagements 7 through 9 build on each other in that order: 8 reuses 7's retrieval functions, and 9
reuses 8's agent runtime. That ordering is a real dependency, not a preference.

---

## 4. Per-project notes

### Engagement 6.1–6.4 — reporting reliability
Read [`spec.md`](spec.md) end to end. It supersedes
[`important_considerations/2026-07-23-trackflow-reporting-reliability-implementation-plan.md`](important_considerations/2026-07-23-trackflow-reporting-reliability-implementation-plan.md);
§9 of the spec lists every deliberate departure and why. Starts with a mandatory read-only
production rescan (§1.3), which needs `services/central-api/.env.production-readonly.local` present
locally — that file is gitignored and will not exist in a fresh clone.

### Engagement 6.5 — sales forecasting
Read [`spec-6.5-sales-forecasting.md`](spec-6.5-sales-forecasting.md). The dataset
(`sales_forcasting/trackflow_sales.csv`) and its deterministic generator were produced during
planning because the assignment's stated source file does not exist and no production source can
supply it; the spec's §1.1 records that deviation. Both files relocate to `data/raw/` and `scripts/`
at implementation time.

### Engagement 7 — RAG knowledge base
Reading order: `context.md`, then `instructions.md`, then the four source documents (`delivery.md`,
`returns_policy.md`, `coverage.md`, `storage_pricing.md`). Note that `context.md` refers to those
sources by different filenames than the ones on disk. Open questions that must be settled in its
spec: vector store choice and hosting, embeddings and generation providers, whether the query
endpoint is a Central API domain or a new service, and whether the Back Office information
architecture is restructured here.

### Engagement 8 — agent engineering
The owner-approved specification is [`docs/agents/agent-design.md`](../../agents/agent-design.md),
which takes precedence over the planning inputs below. Phases 0–6 were accepted and the engagement
was closed by the owner on August 3, 2026. The Codespaces-specific MCP exercise was waived at
closeout and was not executed or passed; safe local evidence is recorded in
[`docs/agents/mcp-owner-review-evidence-2026-08-03.md`](../../agents/mcp-owner-review-evidence-2026-08-03.md).

Five sequential parts: LangGraph migration (01), tools (02), MCP server with OAuth (03), guardrails
(04), memory (05). Each has a `_context.md` and/or `_instructions.md`. **The guardrails part must
precede the memory part** — the assignment states why, and the reason is sound: persistent memory
without guardrails turns a single injection into permanent poisoning. Depends on Engagement 7's
`retrieve()` and `generate_answer()` being separately callable.

### Engagement 9 — agentic workflows
**Status: ✅ Delivered — merged to `main` and deployed to production on 2026-08-17 (RFP Desk + agent Ask-AI live and verified). Retained here for planning history.**

Read `agentic_workflows_context.md` first — it governs all three parts. Three sequential parts:
intake and routing (01), response generation (02), approval and document completion (03).
**This is LangGraph work, not n8n**, despite what older roadmap entries say.

### Engagement 10 — real-time dashboards and alerts
⛔ `10_realtime/realtime.md` is **empty**. There are no requirements. Do not begin planning or
implementation until requirements exist.

### Cross-cutting backlog
[`others.md`](important_considerations/others.md) holds three real items that are not an engagement
of their own: persisting website contact-form leads, adding a job-applicant form and migrating
talent data off the third-party 4Geeks API, and restructuring the Back Office information
architecture. Fold each into whichever engagement forces it rather than creating a new engagement
number. The contact-form and applicant work introduces the platform's **first real personal data**,
which retires the disposable-data waiver and requires backup and retention decisions first.

---

## 5. What does not live here

- **Stakeholder briefs** stay at `docs/briefs/NN-<slug>.md`. `AGENTS.md` requires reading the active
  brief before implementation, and `.agents/skills/start-engagement/SKILL.md` is the workflow for
  creating one. A planning input is not a brief, and an approved spec does not replace one.
- **Standards** stay in `docs/standards/`; scoped agent rules stay in `.agents/rules/`. Apply every
  rule whose scope matches the files being touched.
- **Runbooks** stay in `docs/runbooks/`.
- **Completed planning artifacts** move to `docs/archive/` when their work is delivered.

---

## 6. Working agreement

- Implementation is **phased**, with an owner review-and-approval pause after every phase.
- Production availability and data come first; no destructive or production-affecting action without
  explicit approval.
- Do not commit, stage, discard, or overwrite existing worktree changes.
- If a spec is ambiguous or appears wrong, say so at plan time rather than resolving it silently.
