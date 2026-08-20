# Company Knowledge Base — RAG source corpus

These four Markdown documents are the **single source of truth** indexed by the Engagement 7 RAG
knowledge base. `setup()` (`data/process/rag.py`) reads this folder, chunks each document by semantic
section, and upserts the chunks into the Qdrant collection `trackflow`.

| File | Content | `source_document` payload value |
|---|---|---|
| `trackflow-sla-delivery.en.md` | Delivery SLA | `sla-delivery` |
| `trackflow-returns-policy.en.md` | Returns policy | `returns-policy` |
| `trackflow-carrier-coverage.en.md` | Carrier coverage | `carrier-coverage` |
| `trackflow-storage-pricing.en.md` | Storage pricing | `storage-pricing` |
| `trackflow-service-pricing.en.md` | Service pricing (last-mile, returns, volume tiers) | `service-pricing` |

Filenames and `source_document` slugs come from
`docs/planning/remaining_planning/07_rag_knowledge_base/context.md` and must not be changed without
re-indexing. To change a policy, edit the file here and re-run the indexer — the RAG system never
invents facts outside these documents.

See `docs/rag/rag-design.md` for the full pipeline design and
`docs/planning/remaining_planning/07_rag_knowledge_base/rag-explainer.md` for a beginner explanation.
