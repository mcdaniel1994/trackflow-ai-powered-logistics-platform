"""Configuration gate for the RFP workflow domain.

Phase 0 exposes only the feature flag. Later phases extend ``is_rfp_configured`` to also require the
provider keys the graph needs (OpenAI for structured decisions, DeepSeek for generation), mirroring
the RAG domain's gate.
"""

from __future__ import annotations

from ...core.config import Settings


def is_rfp_configured(settings: Settings) -> bool:
    """True only when the RFP workflow is enabled for this deployment."""
    return bool(settings.rfp_enabled)
