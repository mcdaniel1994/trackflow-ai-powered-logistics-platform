"""Safe routing-model token accounting for Agent OS traces.

Prices are explicit and model-specific. They are not inferred from model names. The current
``gpt-4o-mini`` rates were verified from OpenAI's official Prompt Caching pricing table on
2026-08-03: https://openai.com/index/api-prompt-caching/ (USD per one million tokens).

Only numeric usage counters are accepted from the provider response. Prompt/completion content and
the raw provider payload never enter graph state or persistence.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: Decimal
    cached_input_per_million: Decimal
    output_per_million: Decimal


@dataclass(frozen=True)
class ModelUsage:
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int = 0
    cost_usd: float | None = None


MODEL_PRICES: dict[str, ModelPrice] = {
    "gpt-4o-mini": ModelPrice(Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
    "gpt-4o-mini-2024-07-18": ModelPrice(Decimal("0.15"), Decimal("0.075"), Decimal("0.60")),
}


def _counter(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _build_usage(usage: Mapping[str, Any], model: str) -> ModelUsage | None:
    """Validate raw numeric counters and price them, or return ``None`` safely.

    Cost is only computed for models in ``MODEL_PRICES``. A model absent from that table (for
    example the DeepSeek ``deepseek-chat`` alias, whose target model — and therefore price — is not
    model-specific and cannot be verified from a name) yields exact token counts with ``cost=None``
    rather than a fabricated cost.
    """
    input_tokens = _counter(usage.get("input_tokens", usage.get("prompt_tokens")))
    output_tokens = _counter(usage.get("output_tokens", usage.get("completion_tokens")))
    total_tokens = _counter(usage.get("total_tokens"))
    if input_tokens is None or output_tokens is None:
        return None
    expected_total = input_tokens + output_tokens
    if total_tokens is None:
        total_tokens = expected_total
    if total_tokens != expected_total:
        return None

    input_details = _mapping(usage.get("input_token_details", usage.get("prompt_tokens_details")))
    cached = _counter(input_details.get("cache_read", input_details.get("cached_tokens", 0)))
    if cached is None or cached > input_tokens:
        return None

    price = MODEL_PRICES.get(model)
    cost: float | None = None
    if price is not None:
        uncached = input_tokens - cached
        million = Decimal(1_000_000)
        computed = (
            Decimal(uncached) * price.input_per_million
            + Decimal(cached) * price.cached_input_per_million
            + Decimal(output_tokens) * price.output_per_million
        ) / million
        cost = float(computed)

    return ModelUsage(input_tokens, output_tokens, total_tokens, cached, cost)


def usage_from_message(message: object, model: str) -> ModelUsage | None:
    """Extract standardized LangChain/OpenAI token counters, or return ``None`` safely."""
    standardized = _mapping(getattr(message, "usage_metadata", None))
    provider = _mapping(_mapping(getattr(message, "response_metadata", None)).get("token_usage"))
    usage = standardized or provider
    if not usage:
        return None
    return _build_usage(usage, model)


def usage_from_counters(usage: Mapping[str, Any] | None, model: str) -> ModelUsage | None:
    """Price already-extracted numeric token counters (e.g. from a raw OpenAI-SDK completion).

    Used for the DeepSeek generation call, which returns OpenAI-style ``prompt_tokens`` /
    ``completion_tokens`` / ``total_tokens`` numbers that the pipeline surfaces as a plain mapping.
    Only numeric counters are accepted; no provider content ever reaches this function.
    """
    if not usage:
        return None
    return _build_usage(usage, model)


def combine_usage(usages: Iterable[ModelUsage | None]) -> tuple[int | None, float | None]:
    """Fold several priced calls into one step's ``(tokens, cost_usd)``.

    Tokens sum across every call that produced counters. Cost sums **only when every present call was
    priced** — if any contributing call has ``cost_usd=None`` (e.g. an unpriced model), the combined
    cost is ``None`` rather than a partial, misleading sum. Returns ``(None, None)`` when no call
    produced usage at all.
    """
    present = [usage for usage in usages if usage is not None]
    if not present:
        return None, None
    tokens = sum(usage.total_tokens for usage in present)
    if all(usage.cost_usd is not None for usage in present):
        cost: float | None = float(sum(usage.cost_usd or 0.0 for usage in present))
    else:
        cost = None
    return tokens, cost
