# Milestone 9 — Agentic Workflow Generation (Part 2 of 3): RFP Response Generation

> **Before you start:** Read
> [`agentic_workflows_context.md`](agentic_workflows_context.md) before writing any code. It
> contains the concrete TrackFlow guidelines your evaluator agents must validate against.

## 🎯 The Challenge

In Part 1, you built a flow that classifies each RFP and opens a ticket for it, making it clear to
Sales what's needed from each department. Now Sales wants to go one step further: turn that
analysis directly into a first draft of the pricing proposal, automatically reviewed before a
human ever sees it.

> **Ticket — RFP response generation and evaluation**
>
> **Context:** Part 1 tells us what needs to be answered in each RFP, but putting together the
> draft of the pricing proposal is still manual and slow. I need the system to generate a first
> draft per department and have that draft self-evaluate before it reaches a human.
>
> **What I need you to build:**
>
> - A generator agent per department that receives the metadata and summary produced in Part 1 and
>   drafts the corresponding section of the pricing proposal.
> - Several evaluator agents running in parallel over each generated section: readability
>   (`py-readability-metrics` works for this), relevance to what the RFP is asking for, and
>   compliance with our company guidelines.
> - If a section fails evaluation, send it back to the corresponding generator with concrete
>   feedback on what to fix. It shouldn't get stuck, and the ticket shouldn't be discarded
>   entirely.
> - An iteration limit on that generator-evaluator loop so it doesn't repeat indefinitely if a
>   generator can't pass evaluation.
> - **Optional:** If you already have the semantic knowledge base set up, give the generator access
>   to it. Drafting with our real policies and tone instead of improvising them makes it much more
>   likely to pass the compliance check on the first try.
>
> **Acceptance criteria:** The handoff to Part 3 must include, for every department, both the
> generated content and the result of its evaluation.
>
> — Your tech lead

### 📚 Complementary Knowledge: Guideline Compliance

When the ticket asks an evaluator to check "compliance with company guidelines," it doesn't mean
a free-form style judgment. [`agentic_workflows_context.md`](agentic_workflows_context.md)
contains a concrete list of rules—tone, data that can't be missing, and figures that must
appear—that the evaluator must check the generated content against, rather than relying on the
agent's subjective opinion.

If TrackFlow's semantic knowledge base is available, it's a good place for the generator to look
up real policies, reference pricing, or brand language before drafting. This reduces how often the
evaluator rejects a section for inventing something that doesn't match what the company actually
says. This is a suggested improvement, not a requirement for Part 2.

### 🗺️ Visual Reference: Departmental Mapping and Deliverable Finalization

This stretch takes the **defined workstream structure** from Part 1, maps tasks to departments
through an **assignment orchestrator**, runs department-scoped generation in parallel, and uses a
**synthesizer** to consolidate outputs into department-specific assignment tickets ready for
evaluation and approval.

## 🌱 How to Start the Project

Continue on the same Milestone 9 work in your monorepo fork, or create
`feature/milestone-9-part-2-rfp-response` from the branch where you submitted Part 1. If you don't
have your fork, create it from the base monorepo.

1. Build on the classification and routing flow from Part 1; don't rewrite it from scratch.
2. Install new dependencies with `uv add`.
3. Review [`agentic_workflows_context.md`](agentic_workflows_context.md) again. It contains the
   concrete guidelines your evaluator agents must validate against.

## 💻 What You Need to Do

### Per-Department Generation

- [ ] Implement a generator agent per department that receives the relevant summary produced in
  Part 1.
- [ ] Make each generator produce content specific to its department's section of the pricing
  proposal.

> **Optional:** If TrackFlow's semantic knowledge base is available, give the generator access to
> it so it drafts with real policies and brand language. This isn't a graded requirement for Part
> 2; it's an improvement that can reduce how often a section is sent back during evaluation.

### Parallel Evaluation

- [ ] Implement multiple evaluator agents that run in parallel over each generated section.
- [ ] Make at least one evaluator check readability; `py-readability-metrics` is suggested.
- [ ] Make at least one evaluator check relevance: the content must answer what the RFP asks for.
- [ ] Make at least one evaluator check compliance with the guidelines defined in
  [`agentic_workflows_context.md`](agentic_workflows_context.md).

### Generator-Evaluator Loop

- [ ] If a section fails evaluation, return it to the corresponding generator agent along with the
  reasons for failure.
- [ ] Define and enforce an iteration limit to prevent the generator-evaluator loop from repeating
  indefinitely.

### Ticket Status

- [ ] Update the ticket created in Part 1 to reflect generation and evaluation progress, using
  statuses such as `drafting` and `under_evaluation`.

> **Important:** The company guidelines used to evaluate generated content and the expected format
> of each section must match
> [`agentic_workflows_context.md`](agentic_workflows_context.md). A generic implementation that
> ignores the context will not be accepted.

### Testing

- [ ] Include unit tests in `tests/pipelines/` for at least one generator agent and one evaluator
  agent, including the case where evaluation fails.

## 🧭 Design Questions

- What state information does each evaluator agent actually need? Are you passing only the section
  it should review or the entire document?
- How do you prevent two parallel evaluators from conflicting when writing their results to shared
  state?
- What happens if a generator agent reaches the iteration limit without passing evaluation? What
  does the ticket show Sales in that case?
- Is the feedback the generator receives after a failure specific enough to fix the real problem,
  or is it generic?

## ✅ What We Will Evaluate

- [ ] Each department has its own generator agent, clearly separated from the others.
- [ ] Evaluators run in parallel and don't block execution across other departments.
- [ ] The system correctly applies the generator-evaluator loop, including the iteration limit.
- [ ] The ticket accurately reflects generation and evaluation progress in real time.
- [ ] Evaluation criteria—readability, relevance, and guidelines—are implemented in a verifiable
  way, not as unstructured free text.
- [ ] Unit tests cover both the success case and the evaluation-failure case.
- [ ] The implementation uses the guidelines and formats defined in TrackFlow's
  [`agentic_workflows_context.md`](agentic_workflows_context.md).

## 📦 How to Submit

This is Part 2 of 3 of Milestone 9. Submit it with its own pull request; don't wait until Part 3 is
ready.

1. Commit and push your `feature/milestone-9-part-2-rfp-response` branch.
2. Open a pull request describing what you implemented and how to test it.
3. Include two generated-section examples in the pull request description: one that passes
   evaluation and one that fails.
4. Request a review from your tech lead.
