# Milestone 9 — Agentic Workflow Generation (Part 3 of 3): Approval & Document Completion

> **Before you start:** Read
> [`agentic_workflows_context.md`](agentic_workflows_context.md) before writing any code. It
> contains TrackFlow's department approval hierarchy and final document format.

## 🎯 The Challenge

In Part 2, each department generates and self-evaluates its section of the pricing proposal within
the same ticket opened in Part 1. What's missing is the most delicate part: a human from each
department has to sign off before the final document goes out to the client.

> **Ticket — Human approval and document completion**
>
> **Context:** We already generate and self-evaluate every section of the proposal, but nobody is
> going to sign a pricing proposal without a human from each department giving the green light.
> This is the last piece of the flow we started in Part 1, and it needs to feel like one continuous
> experience, not three projects taped together.
>
> **What I need you to build:**
>
> - Before a department's section is considered approved, the flow must go through a real human
>   approval point—an actual human-in-the-loop, not just one more automatic evaluator.
> - The flow must pause immediately before that irreversible action, persist its state with a
>   checkpointer, and resume exactly where it left off once approval arrives, rather than
>   restarting from scratch.
> - That pause should affect only the branch for the department waiting on approval. Other
>   departments whose sections are ready should keep moving in parallel rather than block one
>   another.
> - Define an iteration limit and an explicit arbitration node for disagreements between
>   departments. Don't let the agents sort it out on their own.
> - Once every department has signed off, generate the final document by consolidating all
>   approved sections.
> - For any run, make it possible to see which agent did what and in what order. When something
>   breaks in production, we won't have time to guess.
>
> Once you're done, run the complete flow end to end—from uploading the RFP in Part 1 to generating
> the final document here—and confirm that it feels like a single process: no strange state jumps,
> mismatched messages between parts, or broken handoffs.
>
> **Acceptance criteria:** An RFP can travel through all three parts end to end, pause for human
> approval per department without blocking the others, and finish with a final document generated
> automatically, with full traceability of every step.
>
> — Your tech lead

### 📚 Complementary Knowledge: When to Interrupt and When to Use a Guardrail

Not every control needs to pause the flow for a human. Guardrails—automated schema, type, or
business validations—should resolve clear-cut cases on their own. Save interruptions
(`interrupt()`) for decisions that genuinely require human judgment, such as approving a pricing
proposal before it goes to a client.

When you interrupt, keep it scoped. The interruption should pause only the branch of the graph that
depends on that approval—the department's section and its dependents—not the entire flow. One
department waiting on its manager's sign-off shouldn't stall other departments that are ready to
move forward.

### 🗺️ Visual Reference: Approval Tickets and Ultimate Document Synthesis

Once the department assignment tickets from Part 2 are **fully approved**, an **ultimate document
synthesizer** compiles the final agreed-upon document and delivers it to Sales. Parallel department
branches approve independently and then converge.

## 🌱 How to Start the Project

Continue on your Milestone 9 work in TrackFlow's monorepo fork, starting from where you submitted
Part 2. If you don't have your fork, create it from the base monorepo.

1. Create the Part 3 branch from your Part 2 branch:

   ```bash
   git checkout -b feature/milestone-9-part-3-approval-completion
   ```

2. Set up the checkpointer appropriate for the repository and environment. Use SQLite or
   PostgreSQL; avoid an in-memory checkpointer outside local development.
3. Install new dependencies with `uv add`.
4. Review [`agentic_workflows_context.md`](agentic_workflows_context.md) for TrackFlow's department
   approval hierarchy.

## 💻 What You Need to Do

### Human Approval per Department

- [ ] Implement an interruption point (`interrupt()`) before a department's section is considered
  approved.
- [ ] Make the interruption pause only the graph branch corresponding to that department, without
  blocking departments that are already done.
- [ ] Persist the flow's state with a checkpointer before each interruption so execution is
  resumable.
- [ ] Implement resume as an explicit entry point into the graph, not as a restart of the entire
  flow.
- [ ] Validate the human response on resume (`approve`, `reject`, or `request changes`) before
  letting it back into the graph.
- [ ] Extend the ticket interface built in Part 1 (`uis/backoffice`) so each department can record
  its approval or rejection.

### Guardrails and Flow Control

- [ ] Define a maximum iteration limit on any remaining loop between departments.
- [ ] Implement an explicit arbitration node to resolve disagreements between departments instead
  of letting agents settle them on their own.
- [ ] Log the agent, input, output, and timestamp in state for every node execution to provide
  traceability.

### Document Completion

- [ ] Once every department has approved, generate the final document by consolidating the
  approved sections.
- [ ] Update the ticket to its final status, such as `done`, and make the generated document
  accessible.

### End-to-End Review

- [ ] Run at least one test RFP through all three complete parts—intake → generation → approval and
  completion—and confirm that ticket states, messages, and data remain consistent from start to
  finish.
- [ ] Fix any state jump, inconsistent message, or data loss in the transitions between parts.

> **Important:** The department approval hierarchy and final document format must match
> [`agentic_workflows_context.md`](agentic_workflows_context.md). A generic implementation that
> ignores the context will not be accepted.

### Testing

- [ ] Include unit tests in `tests/pipelines/` covering successful interruption and resume, the
  iteration limit being reached, and arbitration on disagreement.

## 🧭 Design Questions

- What happens if a department rejects its section after interruption? Does the flow go back to
  the Part 2 generator, or does it require a new run?
- How do you namespace `thread_id` so concurrent runs from different RFPs don't corrupt one
  another's checkpoints?
- What's the minimum information a human needs to see at the approval point to decide with
  confidence, without rereading the entire document?
- If two interdependent departments return contradictory results, who arbitrates, and by what
  rule?

## ✅ What We Will Evaluate

- [ ] The flow correctly pauses before each department's approval and persists its state.
- [ ] The pause affects only the corresponding department branch; other departments can keep
  moving without being blocked.
- [ ] Execution resumes exactly from the interruption point without restarting the entire flow.
- [ ] An iteration limit is applied and verifiable in code, not just mentioned.
- [ ] An explicit arbitration node exists for disagreements between departments.
- [ ] Every node execution is logged with agent, input, output, and timestamp.
- [ ] The final document is generated automatically only after every active department approves.
- [ ] The ticket reflects the process's final status and provides access to the generated document.
- [ ] A test RFP can be traced end to end from Part 1 through Part 3 with no state jumps or visible
  inconsistencies.
- [ ] Unit tests exist for interruption/resume, the iteration limit, and arbitration.

## 📦 How to Submit

This is Part 3 of 3 of Milestone 9. Submit it with its own pull request.

1. Commit and push your `feature/milestone-9-part-3-approval-completion` branch.
2. Open a pull request describing what you implemented and how to test it.
3. Include a complete example in the pull request description: the input RFP, simulated approval
   from each department, and the generated final document.
4. Request a review from your tech lead.
