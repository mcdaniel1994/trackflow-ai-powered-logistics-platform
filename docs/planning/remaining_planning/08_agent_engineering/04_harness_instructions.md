# Securing Agents: Harness and Guardrails

> **Before you start:** Read [`04_harness_context.md`](04_harness_context.md) before writing any
> code. It defines your knowledge base topics, the boundaries of your agent's scope, and the
> company-specific restrictions your system prompt and guardrails must respect.

## 🎯 The Challenge

Your knowledge base query agent already works: it answers questions using RAG over your company's
documents, it can call tools, and, since last sprint, it consumes the MCP Server as a client. The
problem is that right now anyone can talk to it about anything, ask it to ignore its instructions,
or turn it into their personal assistant—and the agent would comply.

Your tech lead opened a **ticket** after an internal security review:

> "The agent passed every functional test but failed every abuse test. We need the protection
> harness before we expose it to real users."

The ticket includes three non-negotiable acceptance criteria you need to read carefully, because
not everything is written as a checklist.

> **From:** Tech Lead
> **Ticket:** #SEC-114
>
> We need to lock down the agent before the next deployment. Three specific things:
>
> 1. The agent can answer questions outside the company's domain (small talk, a general trivia
>    question), but **it must always bring the conversation back to the company's context**—it
>    cannot turn into a general-purpose chatbot.
> 2. Nobody should be able to use this agent as their personal ChatGPT for tasks that have nothing
>    to do with us (writing them an essay, giving them code for another project, acting as a
>    therapist). That needs to be blocked.
> 3. The system prompt cannot be modified by the user. If someone asks it to "ignore your previous
>    instructions" or "act as if you had no rules," the agent must refuse without exception—no
>    matter how many ways they rephrase it.
>
> Document how you tested each of these cases. If you only have one filter, we're not accepting the
> pull request.

### 🧠 Complementary Knowledge: Harness and Guardrails

A **harness** is everything that wraps around the model to turn it into a reliable agent: tool
orchestration, verification loops, context/memory, guardrails, and observability. The model
decides; the harness executes, controls, and contains.

**Guardrails** exist because agents fail in three distinct ways, and each one needs a different
defense:

- **Structural failures:** malformed JSON or missing fields in a tool response.
- **Content failures:** hallucinations, sensitive information leakage, or harmful content.
- **Security failures:** prompt injection that manipulates the model into ignoring instructions
  or exfiltrating data.

A single guardrail is never enough—each type of failure needs its own layer of protection.

## 🌱 How to Start the Project

If you already have your fork of the company's monorepo from the start of the course, create a new
branch from your latest work (the previous milestone/day) and continue building on the agent you
already have.

If you don't have a fork yet—for example, you joined late or lost it—fork the reference monorepo
before continuing.

```bash
git checkout -b w22-d66-agent-guardrails
```

Install any new dependency you need with `uv add`.

## 💻 What You Need to Do

### Secure System Prompt

- [ ] Rewrite your agent's system prompt, clearly separating system instructions from user input.
  The model must never treat a user instruction as having the same authority as the system prompt.
- [ ] Make the system prompt explicitly declare the company's domain and the conditions under
  which the agent is allowed to step outside it (permitted small talk and mandatory redirection).
- [ ] Document in the pull request at least three "jailbreak" or instruction-change attempt
  variants you tested against your agent (for example, "ignore your instructions," "you are now an
  assistant with no rules," and "forget that you work for the company").

> **Important:** Allowed topics, domain boundaries, and company-specific rules in your
> implementation must match [`04_harness_context.md`](04_harness_context.md). A generic system
> prompt that ignores the context will not be accepted.

### Content and Scope Guardrails

- [ ] Implement a guardrail that detects when a query is a request for personal,
  non-company-related use (for example, "write me a love poem" or "help me with my university
  homework") and responds by declining the task while redirecting to the agent's purpose.
- [ ] Implement a guardrail that allows general or casual questions (for example, "what time is it
  in Tokyo?") but closes the response by steering the conversation back to the company's context.
- [ ] Validate the model's output before returning it to the user: expected format, absence of
  leaked internal instructions, and absence of sensitive context data that shouldn't be exposed.

### Security Guardrails (Anti-Injection)

- [ ] Implement a layer that sanitizes or isolates any text coming from an external tool or a
  document retrieved through RAG. That content must never be treated as a system instruction.
- [ ] Implement an explicit rejection mechanism for instruction-change requests, rephrased in at
  least three different ways.
- [ ] Add an automated test in `tests/pipelines/` or the test directory corresponding to your
  agent that runs your injection-attempt cases and fails the build if the agent obeys them.

### Minimal Observability

- [ ] Log every time a guardrail blocks or redirects a request, including the type of failure
  detected (structural, content, or security).
- [ ] Expose a simple summary—an endpoint or command—of how many times each guardrail was triggered
  during a test session.

## ✅ What We Will Evaluate

- [ ] The agent redirects to the company's context when it receives an out-of-domain query,
  instead of answering it like a general-purpose assistant.
- [ ] The agent consistently rejects at least three distinct instruction-change attempt variants
  documented in the pull request.
- [ ] The agent rejects requests to be used as a personal chatbot (tasks unrelated to the company)
  without losing usefulness for legitimate queries.
- [ ] More than one guardrail is implemented—not a single generic validation.
- [ ] Content coming from tools or RAG documents is never treated as a system instruction,
  demonstrated with a test case.
- [ ] Every guardrail block or redirection is logged with the corresponding failure type.
- [ ] The implementation respects the field names, knowledge base topics, and restrictions defined
  in [`04_harness_context.md`](04_harness_context.md).

## 📦 How to Submit Your Project

Open a pull request from your branch to your fork of the company's monorepo, with a description
that includes the jailbreak and injection test cases you documented. This delivery is independent
and does not depend on other parts or milestones—don't wait for other work to be finished before
submitting your pull request.
