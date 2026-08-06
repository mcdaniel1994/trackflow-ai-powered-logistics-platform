"""RAG knowledge query service: the single boundary between HTTP and the pipeline.

The router owns no retrieval or generation logic. This service checks configuration, delegates
to the pipeline's ``query()`` (retrieve -> prompt -> generation), and translates pipeline
failures into a typed domain error the app boundary renders as HTTP.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pipelines.rag import RagPipelineError, query  # type: ignore[import-untyped]

from ...core.config import Settings
from .config import build_rag_config, is_rag_configured

logger = logging.getLogger(__name__)


@dataclass
class RagError(Exception):
    """Typed RAG failure translated to HTTP only at the application boundary."""

    status_code: int
    detail: str


class RagService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def answer(self, question: str) -> str:
        """Return a model-generated answer for the question, or raise a typed RagError."""
        if not is_rag_configured(self.settings):
            raise RagError(503, "The knowledge base is not available right now.")
        config = build_rag_config(self.settings)
        try:
            return str(query(question, config))
        except RagPipelineError:
            # Keep provider and vector-store internals out of the client response and logs.
            logger.warning("rag_query_failed")
            raise RagError(502, "The knowledge assistant is temporarily unavailable.") from None
        except Exception:
            # Backstop: no provider/vector-store fault should ever surface to the client as a 500.
            logger.warning("rag_query_unexpected_error")
            raise RagError(502, "The knowledge assistant is temporarily unavailable.") from None
