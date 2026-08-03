"""Index the company knowledge base into Qdrant (Engagement 7).

Runs the RAG pipeline's ``setup()`` against ``docs/company-knowledge-base/`` using Central
API settings for provider keys and the Qdrant location. Idempotent by default (deterministic
point IDs); pass ``--recreate`` to drop and rebuild the collection.

Usage:
    python -m scripts.rag_index [--recreate] [--corpus-dir PATH]
"""

from __future__ import annotations

import argparse
import logging
import sys

from pipelines.rag import setup  # type: ignore[import-untyped]

from central_api.core.config import get_settings
from central_api.domains.rag.config import build_rag_config

logger = logging.getLogger(__name__)


def entrypoint() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Index the TrackFlow knowledge base into Qdrant.")
    parser.add_argument("--recreate", action="store_true", help="Drop and rebuild the collection.")
    parser.add_argument("--corpus-dir", default=None, help="Override the corpus directory.")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.openai_api_key:
        print("OPENAI_API_KEY is required to embed the corpus.", file=sys.stderr)
        raise SystemExit(1)

    config = build_rag_config(settings)
    result = setup(config, corpus_dir=args.corpus_dir, recreate=args.recreate)
    print(
        f"Indexed collection '{result.collection}': "
        f"{result.documents} documents -> {result.chunks} chunks."
    )


if __name__ == "__main__":
    entrypoint()
