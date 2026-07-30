"""Evaluate the RAG knowledge base against data/eval/rag/test-queries.json (Engagement 7).

Measures Recall@3 (does the expected source_document appear in the top-3 retrieval?) and a
simple faithfulness check (does the generated answer contain the required facts and avoid the
forbidden promises?). Requires a live Qdrant plus the embedding and generation providers, so it
is a manual verification tool, not a CI test.

Usage:
    python -m scripts.rag_eval
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pipelines.rag import query, retrieve  # type: ignore[import-untyped]

from central_api.core.config import get_settings
from central_api.domains.rag.config import build_rag_config, is_rag_configured

EVAL_FILE = Path(__file__).resolve().parents[3] / "data" / "eval" / "rag" / "test-queries.json"


def entrypoint() -> None:
    settings = get_settings()
    if not is_rag_configured(settings):
        print("RAG is not configured (need RAG_ENABLED=true, OPENAI_API_KEY, DEEPSEEK_API_KEY).", file=sys.stderr)
        raise SystemExit(1)

    config = build_rag_config(settings)
    dataset = json.loads(EVAL_FILE.read_text(encoding="utf-8"))
    k = int(dataset.get("k", 3))
    queries = dataset["queries"]

    recall_hits = 0
    faithful = 0
    for case in queries:
        chunks = retrieve(case["question"], k=k, config=config)
        sources = {chunk.get("source_document") for chunk in chunks}
        hit = case["source_document"] in sources
        recall_hits += int(hit)

        answer = query(case["question"], config)
        includes = all(fact.lower() in answer.lower() for fact in case.get("must_include", []))
        avoids = all(bad.lower() not in answer.lower() for bad in case.get("must_not_promise", []))
        ok = includes and avoids
        faithful += int(ok)

        print(f"[{'R' if hit else ' '}{'F' if ok else ' '}] {case['id']}: {answer[:90]}")

    total = len(queries)
    print(f"\nRecall@{k}: {recall_hits}/{total} = {recall_hits / total:.0%} (target >= 80%)")
    print(f"Faithful:  {faithful}/{total} = {faithful / total:.0%}")


if __name__ == "__main__":
    entrypoint()
