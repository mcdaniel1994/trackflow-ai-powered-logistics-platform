---
name: start-engagement
description: Use when initializing a new TrackFlow engagement. Creates docs/briefs/NN-<slug>.md from the stakeholder-voice template, updates the README roadmap row, docs/briefs/README.md index, CLAUDE.md "Where New Engagement Code Goes" entry, and memory-bank/progress.md Active/Completed status, and scaffolds the deliverable folder README when a path is provided.
---

# Start Engagement

## Objective

Initialize a new engagement `NN` end-to-end. The primary deliverable is a complete, implementation-ready stakeholder brief at `docs/briefs/NN-<slug>.md` in the same voice and depth as existing briefs (e.g. [02-inventory-carriers.md](../../../docs/briefs/02-inventory-carriers.md), [04-ai-driven-engineering.md](../../../docs/briefs/04-ai-driven-engineering.md)). After the brief is written, the README roadmap, briefs index, `CLAUDE.md`, and memory bank are updated so the repo stays coherent.

The brief is the main artifact. The index updates are supporting work.

## Input Model

The user may invoke this skill with either shape:

- **Structured fields** — the five required metadata fields below, supplied directly.
- **A long stakeholder/project summary** — e.g. an email, meeting notes, a Slack thread, or a paragraph describing the engagement. The skill parses it and extracts the required metadata.

Required metadata (regardless of input shape):

- Engagement number `NN`
- Short slug
- Stakeholder name (and role, if available)
- One-line summary
- Intended deliverable path

Rules for filling required metadata:

- If a field can be safely inferred from the input and repo context, infer it. Examples: the next `NN` from `docs/briefs/README.md`; the deliverable path from precedent in `CLAUDE.md` "Where New Engagement Code Goes"; the slug from the one-line summary.
- Ask the user only when a required detail cannot be safely inferred or when an ambiguity would change scope. Do not require the user to pre-fill a template — this skill creates the brief.

## Workflow

1. Read `README.md`, `AGENTS.md`, `CLAUDE.md`, all three `memory-bank/` files, and `docs/briefs/README.md` to understand current status and conventions. Skim two existing briefs (e.g. [02-inventory-carriers.md](../../../docs/briefs/02-inventory-carriers.md), [04-ai-driven-engineering.md](../../../docs/briefs/04-ai-driven-engineering.md), or [03-talent-pipeline-tracker.md](../../../docs/briefs/03-talent-pipeline-tracker.md)) as style references for tone, headings, and depth.
2. Extract or confirm the five required metadata fields from the input. Infer where safe; ask only for missing pieces that affect scope.
3. Draft a full stakeholder brief at `docs/briefs/NN-<slug>.md` containing every section below — not a placeholder skeleton:
   - **Title** — `# Brief: <Engagement Title>`
   - **Client / stakeholder line** — `## Client: TrackFlow · Stakeholder: <Name> (<Role>)`
   - **`## Status`** — e.g. `In progress — Engagement NN.` or `Upcoming — Engagement NN.`
   - **`## Background`** — situate the engagement in TrackFlow's roadmap and prior milestones
   - **`## Stakeholder Request`** — direct stakeholder voice, ideally a quote block, preserving the original ask
   - **`## Assignment`** — restate the work in implementation terms
   - **`## What You're Building`** — concrete components, files, or behaviors, broken into subsections when useful
   - **`## Acceptance Criteria`** — verifiable conditions for "done"
   - **`## Out of Scope`** — explicit non-goals
4. Add the row to `docs/briefs/README.md` with status `⏳ Upcoming` (or another status the input clearly states).
5. Add the row to the `README.md` roadmap table.
6. Add the entry to `CLAUDE.md` "Where New Engagement Code Goes", pointing at the brief.
7. Update `memory-bank/progress.md`: move the prior Active entry to Completed if applicable; mark the new engagement as Active.
8. If the deliverable path is known and the folder does not yet exist, scaffold it with a `README.md`.

## Brief Authoring Guidance

- Use the existing briefs in `docs/briefs/` as style references for tone, headings, and depth.
- Preserve stakeholder voice — quote the original request where it carries intent. The brief should read like the stakeholder asked for it, not like a template.
- Expand the long summary into the brief's sections rather than dumping it verbatim into one section.
- Do not invent hard requirements that were not provided. When a detail is unclear and affects scope, ask before writing it; otherwise mark it as an explicit assumption in the relevant section.
- The brief must be implementation-ready: a future agent should be able to start work from the brief alone.

## Expected Output

- A new `docs/briefs/NN-<slug>.md` that is a full stakeholder brief — all required sections present, with real content drawn from the stakeholder input. Not a placeholder.
- Updated index rows in `README.md`, `docs/briefs/README.md`, `CLAUDE.md`, and `memory-bank/progress.md`.
- A scaffolded deliverable folder `README.md` when the deliverable path is known.

## Acceptance Criteria

- `docs/briefs/NN-<slug>.md` exists and contains all required sections (Title, Client/Stakeholder, Status, Background, Stakeholder Request, Assignment, What You're Building, Acceptance Criteria, Out of Scope) with concrete content, not placeholder prose.
- The brief preserves stakeholder voice (a quoted request or equivalent direct attribution).
- The brief's Acceptance Criteria are verifiable conditions, not restatements of the assignment.
- `docs/briefs/README.md` has a row for the new engagement with appropriate status.
- `README.md` has a roadmap row for the new engagement.
- `CLAUDE.md` has a "Where New Engagement Code Goes" entry for the new engagement.
- `memory-bank/progress.md` reflects the new Active engagement and does not leave an obsolete Active engagement in place.
- The deliverable folder `README.md` exists when an intended deliverable path was provided.

## Example Invocation

```
/Start Engagement
```

Then paste a long stakeholder request (email, meeting notes, Slack thread, etc.) and ask the agent to extract the metadata and create the full brief. The agent infers what it can from repo context (next `NN`, conventions, deliverable path precedents) and asks only for missing details that affect scope.

## Verification Method

Open this `SKILL.md` and confirm each required section is present and concrete. Verify the skill by static inspection only. Do not create a fake `99-dry-run` engagement because that would mutate the repository.
