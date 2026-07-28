# Milestone 8 — Agent Memory and Self-Improvement

> **Before you start:** Read [`05_memory_context.md`](05_memory_context.md). It defines what
> information must never enter your agent's memory and what kinds of facts are actually worth
> remembering at TrackFlow.

## 🎯 The Challenge

Your agent already knows the company through RAG, calls tools through the MCP Server, and stays
inside its security guardrails. The problem is that every conversation starts from zero: it
doesn't remember that a similar escalation was resolved yesterday or that a user already corrected
a piece of data last week. Your tech lead opened a **ticket** after two different clients had to
repeat the same correction three times in the same week.

It's not a coincidence that this project comes right after the guardrails sprint, rather than
before. Without guardrails, a manipulation attempt damages a single conversation; with persistent
memory but no prior protection, that same attempt could get written into the memory store and
repeat itself in every future conversation—the error stops being a one-off and becomes cumulative.
That's why the agent was hardened against manipulation in the previous sprint first, and only now
does it gain the ability to remember and self-improve.

### 🧠 Complementary Knowledge: Memory Architectures

An agent's memory isn't a single component—it's organized by temporal scope:

- The context window is enough when the task fits in a single session.
- Episodic memory (Redis, key-value storage, or prompt caching) lets the agent remember past
  interactions and personalize.
- A vector database retrieves semantically similar information across large corpora.
- Knowledge graphs matter when explicit relationships (dependency, hierarchy) are the actual
  retrieval requirement—something cosine similarity can't capture.
- Fine-tuning (parametric memory) is the last resort: it's expensive, slow to update, and doesn't
  let you selectively "forget."

No self-improving memory architecture works without a cleanup and consolidation cycle. Without
curation, raw accumulation degrades retrieval quality over time.

> **From:** Tech Lead
> **Ticket:** #MEM-092
>
> The agent already knows the company, uses the MCP Server's tools, and stays inside its
> guardrails. But every conversation starts from zero: it doesn't remember that we resolved a
> similar escalation yesterday, or that someone already corrected a piece of data last week. I
> need the agent to learn from interaction, without that meaning it starts making things up or
> piling junk into its memory forever.
>
> You don't need a new graph or a multi-agent architecture for this—it's the same agent as always,
> with one extra self-evaluation step:
>
> 1. When the agent detects, within its own response, something worth remembering, it proposes it
>    to the user in the same conversation ("want me to remember this for next time?") instead of
>    writing it straight to memory.
> 2. That decision—yes, no, or an edit—can't be a fuzzy interpretation of the next message. It has
>    to be explicitly classified against the pending proposal and logged: what was proposed, what
>    the user decided, and when. If the decision can't be determined with reasonable confidence,
>    the proposal is discarded by default. Approval is never assumed from silence or ambiguity.
> 3. Only what's approved and logged gets consolidated into the persistent store. What's rejected
>    is discarded, but the record that it was proposed and rejected stays.
>
> I won't accept a memory that grows without limit, that self-edits without the user knowing, or a
> memory write with no trace of who authorized it.

## 🌱 How to Start the Project

1. If you already have your fork of the company's monorepo, create a new branch from your latest
   progress (the previous milestone or day).
2. If you don't have a fork—for example, you joined late or lost it—fork the reference monorepo
   before continuing.
3. Create the working branch:

   ```bash
   git checkout -b w23-d67-agent-memory
   ```

4. Keep building on the same LangGraph agent that already exposes the MCP Server and applies
   guardrails. This project doesn't replace that base; it extends it.
5. Install any new dependency with `uv add`, never `pip install` or `pipenv`.

## 💻 What You Need to Do

### Memory Architecture Selection

- [ ] Choose a persistent memory backend (for example, Redis, a key-value store, a vector
  database, or a combination) and document why it fits what your agent needs to remember at
  TrackFlow.
- [ ] Implement an explicit read/write memory interface. The agent must not accumulate state by
  simply appending everything to the system prompt.

> **Important:** Which facts are memorable and which are strictly forbidden to store must match
> exactly what's specified in [`05_memory_context.md`](05_memory_context.md). A generic
> implementation that ignores those restrictions will not be accepted.

### Self-Evaluation and Memory Proposal

- [ ] After each relevant interaction, make the agent self-evaluate whether there's something new
  or corrected worth remembering, using an explicit criterion rather than simply proposing memory
  after every interaction.
- [ ] The simplest approach is to ask the model for **structured output in a single call**: the
  response the user sees plus a `memory_proposal` field containing, when applicable, what would be
  added or changed and why. You don't need a second model call, a separate agent, or a multi-agent
  architecture—it's the same agent with one additional output field.
- [ ] Make the agent dismiss most interactions as "nothing to remember." Document at least three
  examples of interactions that should **not** generate a proposal.
- [ ] When there is something memorable, make the agent **propose it to the user within its own
  response**—for example, as a question at the end. It never writes directly to memory at this
  step.

### User Confirmation and Auditable Log

- [ ] When there's a pending memory proposal, evaluate the user's next message against that
  proposal first: does it approve, reject, or edit it? Reuse the same kind of intent
  classification you implemented for sensitive responses in the guardrails sprint, rather than a
  naive plain-text match for "yes."
- [ ] Allow only **one pending proposal at a time**. If one is already unresolved, the agent must
  not launch a second one until the first is closed.
- [ ] If the user changes the topic without clearly responding yes or no, discard the proposal by
  default. Approval is never assumed from silence or ambiguity.
- [ ] Log every decision—proposal, outcome, originating message, and timestamp—in an auditable way,
  regardless of whether the proposal was approved or rejected.
- [ ] After resolving the pending proposal, in the same turn or a later one, continue the
  conversation normally. This includes cases where the user answers the proposal and asks another
  question in the same message.

### Consolidation and Cleanup

- [ ] Implement a consolidation mechanism that keeps memory from growing without control, such as
  summarizing, deduplicating, or discarding low-relevance entries.
- [ ] Document the expiration or cleanup policy you applied and why you chose it.

### Evidence

- [ ] Document at least two complete cycles of the flow:
  - One in which a memory update is approved and reflected in a future interaction.
  - One in which a memory update is rejected and memory stays unchanged.

## 🎨 Design Decisions

As part of the challenge, your implementation must resolve—without being told explicitly in a
checklist—the following decisions:

- What kind or kinds of memory (episodic, semantic/vector, or knowledge graph) does TrackFlow
  actually need, and why did you rule out the other options?
- What information should never enter the agent's memory, no matter who asks for it? Check
  [`05_memory_context.md`](05_memory_context.md) for TrackFlow's non-negotiable restrictions.
- How does the agent decide what to forget, and what happens to a pending proposal if the user
  never responds?
- How do you prevent a malicious user from "poisoning" the agent's memory with false information
  presented as a legitimate correction?
- Why doesn't this self-evaluation and memory-proposal flow require a multi-agent architecture?
  Justify your answer with what you implemented.

## ✅ What We Will Evaluate

- [ ] The chosen memory architecture is justified in writing and matches what the agent actually
  needs to remember.
- [ ] There's an explicit read/write memory interface, not implicit memory through the system
  prompt.
- [ ] The agent correctly distinguishes memorable interactions from non-memorable ones, with at
  least three documented examples of each type.
- [ ] The memory proposal is communicated within the same conversation, not through a separate
  channel or process.
- [ ] No memory update is written without an explicit, correctly classified user decision—not a
  naive text match.
- [ ] Only one proposal is pending at a time, and silence or ambiguity resolves as rejection by
  default, not approval.
- [ ] Every proposal and its outcome are logged in an auditable way, regardless of whether it was
  approved or rejected.
- [ ] There's a documented, functional consolidation and cleanup mechanism.
- [ ] At least two complete evidence cycles are delivered: one approved and one rejected.
- [ ] The design decisions explicitly address the restrictions in
  [`05_memory_context.md`](05_memory_context.md), especially what must never be remembered.

## 📦 How to Submit

Follow the standard pull request flow against your own fork of the monorepo:

- [ ] Open a pull request from `w23-d67-agent-memory` to your `main` branch.
- [ ] Include in the pull request description the justification for your memory architecture and
  the answers to the design decisions.
- [ ] Attach or describe the evidence for both complete cycles (approved and rejected).
