# Engagement 7 — RAG Knowledge Base

**Stakeholder:** Miguel Torres, Commercial Director

## Problem

My eight account managers and BD reps answer the same prospect questions all day — delivery SLAs,
returns, carrier coverage, storage pricing — and the answers already exist in our standard
agreements. People still lose time digging, and worse, they occasionally promise terms that aren't in
the contract. I want an assistant anyone on the commercial team can ask in plain language, that
answers **like a TrackFlow salesperson would** — with exact figures and never inventing terms.

## Scope

- A knowledge base built from our four policy documents (delivery SLA, returns, carrier coverage,
  storage pricing), indexed for semantic search.
- An assistant that retrieves the relevant policy text and has a model write the answer from it. The
  raw search result must never be shown directly.
- A query box on the Back Office home page, plus an "Ask AI" entry point, so it's the first thing the
  team sees.
- While we're in there: reorganise the Back Office navigation. It mixes business and technical views
  and is getting cluttered. Group it by category, add a Business ↔ Technical/Agent-OS toggle, and put
  the account menu where people expect it (top-right).

## Non-negotiable business rules

- Never promise a delivery SLA on declared high-demand dates (Black Friday, Christmas, January Sales).
- International returns are always handled manually — never described as automatic.
- No storage discount is offered without saying it needs my approval.
- If the documents don't cover a question, say so honestly. Never invent a figure.

## Acceptance criteria

- All four documents indexed; each produces at least three coherent chunks.
- Recall@3 ≥ 80% on a test set of at least eight questions covering all four documents, including a
  high-demand-peak question.
- Faithfulness: no percentage, rate, or timeframe in an answer differs from the source.
- The final answer is always model-generated from the retrieved context, exposed via a single API
  endpoint the query box calls. Retrieval and generation logic are modular and independently
  swappable.

## Status

✅ **Complete — merged to `main` and deployed to production on 2026-08-17.** `RAG_ENABLED` with provider
keys and a provisioned Qdrant (indexed via `rag-index`); it grounds the Engagement 9 RFP Desk and powers
the agent Ask-AI. Delivered: the corpus (`docs/company-knowledge-base/`), the chunking + `setup`/`embed`/`retrieve`/`query`
pipeline (`data/process/rag.py`, `data/pipelines/rag.py`), the `POST /knowledge/query` endpoint
(`services/central-api/central_api/domains/rag/`), the eval set (`data/eval/rag/test-queries.json`), unit
and endpoint tests, the Back Office refactor + Ask-AI UI (`uis/backoffice/`), and design docs
(`docs/rag/rag-design.md`). Embedding model: OpenAI `text-embedding-3-small`; generation model:
DeepSeek `deepseek-chat`; vector store: self-hosted Qdrant (collection `trackflow`).

**Still required before this is live:** owner review of the approach; provider API keys
(`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`) and a provisioned Qdrant instance; running `rag-index` and the
`rag-eval` Recall@3/faithfulness check against live services. The endpoint returns `503` until
`RAG_ENABLED=true` and both keys are configured. See
[`../planning/remaining_planning/07_rag_knowledge_base/implementation-plan.md`](../planning/remaining_planning/07_rag_knowledge_base/implementation-plan.md).
