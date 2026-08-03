"""Adapt Central API settings into the RAG pipeline's config object.

Keeps the environment-to-pipeline mapping in one place so the query endpoint and the
indexing CLI build identical configuration.
"""

from __future__ import annotations

from pipelines.rag import RagConfig  # type: ignore[import-untyped]

from ...core.config import Settings


def is_rag_configured(settings: Settings) -> bool:
    """True only when RAG is enabled and both provider keys are present."""
    return bool(settings.rag_enabled and settings.openai_api_key and settings.deepseek_api_key)


def build_rag_config(settings: Settings) -> RagConfig:
    """Translate validated Central API settings into a pipeline RagConfig."""
    return RagConfig(
        qdrant_url=settings.qdrant_url,
        qdrant_api_key=settings.qdrant_api_key,
        collection=settings.rag_collection,
        openai_api_key=settings.openai_api_key,
        embedding_model=settings.rag_embedding_model,
        embedding_dim=settings.rag_embedding_dim,
        deepseek_api_key=settings.deepseek_api_key,
        deepseek_base_url=settings.deepseek_base_url,
        generation_model=settings.rag_generation_model,
        top_k=settings.rag_top_k,
        min_score=settings.rag_min_score,
    )
