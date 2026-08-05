"""Configuration for the RFP workflow domain.

Two gates: ``is_rfp_configured`` is the feature flag that turns the domain (and its owner-scoped
reads) on; ``is_rfp_intake_configured`` additionally requires the OpenAI key the classifier,
metadata extractor, and department workers need. Reads never require a provider key; only upload and
intake do. ``RfpConfig`` carries the provider settings into the graph without placing them in graph
state (mirroring the Engagement 8 config split).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...core.config import Settings


@dataclass(frozen=True)
class RfpConfig:
    """Everything the intake/routing graph needs for one run."""

    model: str
    timeout_seconds: float
    openai_api_key: str = field(repr=False, default="")


def is_rfp_configured(settings: Settings) -> bool:
    """True when the RFP workflow is enabled for this deployment (reads are allowed)."""
    return bool(settings.rfp_enabled)


def is_rfp_intake_configured(settings: Settings) -> bool:
    """True only when intake can run: the feature is enabled AND the OpenAI key is present."""
    return bool(is_rfp_configured(settings) and settings.openai_api_key)


def build_rfp_config(settings: Settings) -> RfpConfig:
    """Translate validated settings into an RfpConfig for the graph."""
    return RfpConfig(
        model=settings.rfp_model,
        timeout_seconds=settings.rfp_llm_timeout_seconds,
        openai_api_key=settings.openai_api_key,
    )
