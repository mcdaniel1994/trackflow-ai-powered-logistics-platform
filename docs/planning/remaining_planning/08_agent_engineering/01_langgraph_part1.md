# Support Agent with LangGraph — Part 1 of 2: Migration and Agent Flow

## 🎯 The Challenge

You already built the four functions of your RAG system (`setup`, `embed`, `retrieve`, `query`)
and exposed them through a FastAPI endpoint. It works, but it's a black box: it takes in a question
and returns an answer, without anyone—including you—being able to see what decisions it made along
the way.

Your tech lead opened a ticket with a clear requirement: before adding any new capability to the
agent (Part 2 of this same project), the reasoning flow has to become explicit as a graph, with
state, nodes, and transitions that can be traced and evaluated independently.

> **Tech lead's note:** "I don't want you to rewrite the RAG logic from scratch—the `retrieve`
> and `embed` you already have work fine. What I want is that same behavior living inside a
> LangGraph graph, with single-responsibility nodes, and every run traced. If I can't see why the
> agent answered what it answered, I can't trust it in production."

Three things are implied in that ticket and are easy to miss:

1. The graph must be compiled before any execution, so structural errors are caught at build time
   rather than in production.
2. The state passed between nodes must be minimal and explicit, not the full conversation history.
3. Every run must produce a queryable trace, not just a final answer.

### Complementary knowledge: from naive loop to graph

A "naive" agent is simply a Python `while` loop: call the model, if it requests a tool run it,
feed the result back, repeat. That works for prototypes, but it doesn't scale: there's no way to
pause, resume, trace a specific step, or test a node in isolation.

LangGraph formalizes that same loop as a state machine: each step is a node, each decision about
where to go next is an edge, and the compiled set is the graph. This is what lets you, in Part 2,
add a new tool without touching the rest of the flow: you just add a node and a conditional edge
that decides when to use it.

## 💻 What You Need to Do

### Agent graph (`services/`)

- [ ] Define the graph's state: the minimum information a node needs to decide the next step
  (user question, retrieval result, partial answer). Don't include the full conversation history
  without justifying why you need it.
- [ ] Model at least these nodes:
  - One that receives the question.
  - One that runs `retrieve` against your knowledge base, reusing the code from
    `data/pipelines/` rather than duplicating it.
  - One that generates the final answer from the already-retrieved context using your generation
    step: `generate_answer(question, context)`, the function you factored out of `query()` in the
    RAG project.
- [ ] Define the edges between nodes based on explicit output conditions, not as a hardcoded fixed
  sequence. Include at least one real condition, not just a straight line. For example:
  - If the question is empty, route to a clear error or `END` instead of retrieving.
  - If `retrieve` returns no context above the threshold, route to a node that answers honestly
    ("I don't have information about that") instead of forcing generation on empty context.

> **Node contract—read carefully:** The retrieval node calls `retrieve()`; the generation node
> calls `generate_answer(question, context)` with the context the retrieval node already produced.
> Do not put the monolithic `query()` (retrieve + generate together) inside a single node—that
> re-runs retrieval and collapses the very flow you were asked to make explicit and traceable. If
> you reuse `query()` directly, it must accept already-retrieved chunks and skip its internal
> `retrieve()`.

- [ ] Compile the graph before any execution. Compilation must fail clearly if there's a
  structural error (an unconnected node, a mistyped state, etc.).
- [ ] Implement checkpointing at every meaningful state transition, so a run can be inspected or
  resumed.

### Tracing and evaluation

- [ ] Instrument the graph so that every run produces a trace: which nodes ran, in what order,
  and what each one produced. You can use a tracing tool (for example, LangSmith) or your own
  structured log if you don't have access to one. What matters is that the trace is queryable
  after the run, not just printed to the console.
- [ ] Write at least three evals: test cases with an input question and a verifiable criterion
  about the answer or trace (for example, "for this question, the retrieval node must run before
  query"). Evals run against the trace, not against a live execution every time.
- [ ] Keep evals in `tests/pipelines/` and make them runnable with a single command.
- [ ] Make at least one eval assert that the answer stays grounded in your existing RAG knowledge
  base (for example, a known policy question returns the expected entity or fact). Trace and
  routing correctness do not replace answer grounding: your agent evals are in addition to your
  existing RAG tests, which must still pass. Grounding remains an acceptance gate—a run with a
  perfect trace but an answer that ignores `CONTEXT` policies is a failure.

### Endpoint (`services/`)

- [ ] Expose the compiled graph through an endpoint (for example, `POST /agent/query`) that
  replaces or coexists with the existing RAG endpoint. The endpoint must not contain its own
  business logic; it only invokes the graph.
- [ ] If the graph fails at any node, respond with a clear error message and never a raw stack
  trace.

> **Important:** The agent's behavior—which documents it retrieves and what it answers—must remain
> correct according to your existing RAG knowledge base. Migrating to LangGraph is not an excuse
> for answers to stop being grounded in your company's data.

## ✅ What We Will Evaluate

- [ ] The graph's state is minimal and explicit; it doesn't carry full history without
  justification.
- [ ] There are single-responsibility nodes for receiving the question, retrieval, and answer
  generation.
- [ ] Edges are defined by output conditions, not hardcoded as a fixed sequence.
- [ ] The graph is explicitly compiled before execution and fails with a clear error on a
  structural problem.
- [ ] There is verifiable checkpointing on at least one state transition.
- [ ] Every run produces a queryable trace, not just a final answer.
- [ ] There are at least three runnable evals in `tests/pipelines/`, with verifiable criteria on
  the trace or answer, and at least one asserts that the answer stays grounded in the `CONTEXT`
  knowledge base.
- [ ] Existing RAG tests still pass—agent evals extend, not replace, answer grounding as an
  acceptance gate.
- [ ] The endpoint invokes the graph without duplicating business logic and handles errors without
  exposing internal details.
- [ ] Nodes call `retrieve` and the generation step separately; no single node re-wraps the
  monolithic `query()` (retrieve + generate).
- [ ] The existing `retrieve`, `embed`, and `query` functions are reused from `data/pipelines/`,
  not rewritten from scratch.

## 📦 How to Submit This Project

This is Part 1 of 2. It is submitted through its own pull request, independent from Part 2's. Part
2 may build on this branch, but it is reviewed separately.

```text
data/
└── pipelines/                    ← existing RAG functions, reused without duplication

services/
└── <agent-service>/              ← LangGraph graph, nodes, endpoint

tests/
└── pipelines/                    ← agent evals
```

1. Push your branch with the structure above and open a pull request to the original repository
   with the `part-1-langgraph` label.
2. Make sure your pull request includes:
   - A screenshot or export of the trace from at least one full run.
   - The output of running the evals (console or file).
