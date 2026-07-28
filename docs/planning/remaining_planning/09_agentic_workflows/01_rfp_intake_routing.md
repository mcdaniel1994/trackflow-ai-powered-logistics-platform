# Milestone 9 — Agentic Workflow Generation (Part 1 of 3): RFP Intake & Routing

> **Before you start:** Read
> [`agentic_workflows_context.md`](agentic_workflows_context.md) before writing any code. It
> defines the departments, RFP format, and TrackFlow-specific guidelines for this milestone.

## 🎯 The Challenge

You already built an agent capable of using tools, remembering context across interactions, and
orchestrating itself securely through an MCP Server. Now TrackFlow needs several agents to work
together to solve a real business problem.

The Sales team receives dozens of RFPs (**Requests for Proposal**) as PDFs every week from clients
asking for a pricing proposal. It struggles to hit deadlines because every request needs input from
several departments, and nobody can tell just by reading the document who needs to be asked what.
Your tech lead assigns you the following ticket: build the first stretch of an agentic workflow
that receives these RFPs, determines whether they really are RFPs, and splits the work across the
right agents.

> **Ticket — Agentic workflow for RFP intake and routing**
>
> **Context:** Sales is missing deadlines because nobody knows, when an RFP comes in, which
> departments to involve or what each one needs. We need to automate that first analysis before we
> even touch generating the proposal itself—that's the next part.
>
> **What I need you to build:**
>
> - A ticket-mode interface where the team can upload the RFP (it always arrives as a PDF) and see
>   its status in real time: `analyzing`, `waiting_for_approval`, `done`, and so on.
> - PDF RFPs are heavy and will get expensive in tokens if we hand them to the agents as-is.
>   Convert them to Markdown as soon as they arrive—something like Microsoft's MarkItDown does
>   this well—before any agent processes them.
> - A first classifier agent that decides whether the document is a legitimate RFP. If it isn't,
>   the flow should stop there without moving on to the rest of the pipeline.
> - For each valid RFP, extract metadata and readability metrics that let us anticipate how long
>   processing will take (`py-readability-metrics` could work for this).
> - Split the rest of the analysis by department using the orchestrator-worker-synthesizer pattern
>   covered in class. I don't want a single agent trying to do it all.
>
> **Acceptance criteria:** Sales should be able to look at the result of a processed RFP and know,
> without reading the original document, what's needed from each department and who to ask.
>
> — Your tech lead

### 📚 Complementary Knowledge: PDFs, Readability, and "Ticket Mode"

Real-world RFPs arrive as PDFs, a format dense in markup and visual noise that burns far more
tokens than necessary when fed directly to an LLM. Converting them to Markdown with a tool such as
MarkItDown before processing cuts that cost and gives your agents cleaner text to work with. Once
the text is in Markdown, `py-readability-metrics` computes indexes such as Flesch-Kincaid or
Gunning Fog. Use these to estimate how expensive each RFP will be to process, not as a note on
literary quality.

"Ticket mode" means every uploaded RFP becomes an entity with a lifecycle—states such as
`analyzing`, `waiting_for_approval`, or `done`—that the frontend can query and refresh, just like a
support ticket.

### 🗺️ Visual Reference: Initial Analysis and Workstream Isolation

This part starts with rapid triage (is this an RFP, and is it complex enough?). An
**orchestrator** then decomposes the primary document into parallel workstreams by section or
department, workers process them independently, and a **synthesizer** consolidates everything into
a defined workstream structure with metadata.

## 🌱 How to Start the Project

Keep working on the fork of TrackFlow's monorepo that you've used since Milestone 1. If you don't
have your fork, create it from the base monorepo.

1. Create a new branch from `main`:

   ```bash
   git checkout -b feature/milestone-9-part-1-rfp-intake
   ```

2. Install new dependencies with `uv add` (for example, `uv add markitdown` and
   `uv add py-readability-metrics`), never with `pip install` or `pipenv`.
3. Build or extend the interface in `uis/backoffice`; don't create a new app.
4. Place agent logic in `services/`, following the pattern used in Milestone 8.
5. Read [`agentic_workflows_context.md`](agentic_workflows_context.md) before defining departments
   or the sample RFP format.

## 💻 What You Need to Do

### Intake Interface (Ticket Mode)

- [ ] Implement an interface in `uis/backoffice` where PDF RFP documents can be uploaded, creating
  a ticket for each one.
- [ ] Make the ticket show its current status (for example, `analyzing`,
  `waiting_for_approval`, or `done`) and update as the flow progresses.

### Document Ingestion and Conversion

- [ ] Convert each RFP from PDF to Markdown before handing it to the agents—MarkItDown from
  Microsoft is suggested—to reduce token usage.
- [ ] Extract metadata from the converted document, such as client, date, and departments
  mentioned.
- [ ] Compute readability metrics that help anticipate processing time;
  `py-readability-metrics` is suggested.

### Classifier Agent

- [ ] Implement a first agent that reads the already-converted document and determines whether
  it's a valid RFP.
- [ ] If the document isn't an RFP, stop the flow and leave the ticket in an explicit `discarded`
  state. Don't fail silently.

### Department Orchestration

- [ ] Implement the orchestrator-worker-synthesizer pattern: the orchestrator breaks the RFP down
  into per-department subtasks.
- [ ] Make each worker agent extract the key aspects relevant to its department.
- [ ] Make a synthesizer agent consolidate the results into a summary that tells Sales what to ask
  each department for.

### Routing

- [ ] Route the classified document toward the rest of the agentic flow.

> **Important:** Department names, RFP format, and classification criteria must match
> [`agentic_workflows_context.md`](agentic_workflows_context.md). A generic implementation that
> ignores the context will not be accepted.

### Testing

- [ ] Include unit tests in `tests/pipelines/` for the classifier agent and at least one worker
  agent.

## 🧭 Design Questions

- What happens if an RFP mentions a department that doesn't exist in
  [`agentic_workflows_context.md`](agentic_workflows_context.md)? How does the classifier agent
  handle it?
- What does each worker agent actually need from shared state? Are you passing the whole document
  or only what's relevant to its department?
- How do you decide that a document isn't an RFP? What criterion do you use, and what happens if
  the agent gets it wrong?
- What happens if two worker agents return contradictory information about the same section?

## ✅ What We Will Evaluate

- [ ] The ticket accurately reflects the flow's real status at every moment (`analyzing`,
  `waiting_for_approval`, `done`, or `discarded`).
- [ ] The classifier agent correctly rejects documents that aren't RFPs without stopping the rest
  of the system.
- [ ] Metadata and readability metrics are computed and stored for every processed document.
- [ ] The orchestrator-worker-synthesizer pattern is implemented with clearly separated agents,
  not a single monolithic agent.
- [ ] The final result identifies, per department, the key aspects and who to approach, verifiable
  against a real test case.
- [ ] Unit tests exist for the classifier agent and at least one worker agent.
- [ ] The implementation uses the departments and RFP format defined in TrackFlow's
  [`agentic_workflows_context.md`](agentic_workflows_context.md).

## 📦 How to Submit

This is Part 1 of 3 of Milestone 9. Submit it with its own pull request against `main`; don't wait
until Parts 2 and 3 are ready.

1. Commit and push your `feature/milestone-9-part-1-rfp-intake` branch.
2. Open a pull request describing what you implemented and how to test it.
3. Include a sample test RFP and the output your flow produces in the pull request description.
4. Request a review from your tech lead.
