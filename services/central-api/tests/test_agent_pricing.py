"""Mocked routing usage accounting; no provider calls or payload persistence."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from central_api.domains.agents.pricing import usage_from_message


def _message(usage: object = None, response_metadata: object = None) -> object:
    return SimpleNamespace(usage_metadata=usage, response_metadata=response_metadata)


def test_complete_standard_usage_computes_documented_cost() -> None:
    result = usage_from_message(
        _message(
            {
                "input_tokens": 1_000,
                "output_tokens": 200,
                "total_tokens": 1_200,
                "input_token_details": {"cache_read": 400},
            }
        ),
        "gpt-4o-mini",
    )

    assert result is not None
    assert result.total_tokens == 1_200
    assert result.cost_usd == pytest.approx(0.00024)


def test_absent_usage_returns_none() -> None:
    assert usage_from_message(_message(), "gpt-4o-mini") is None


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": "100", "output_tokens": 2, "total_tokens": 102},
        {"input_tokens": 100, "output_tokens": -1, "total_tokens": 99},
        {"input_tokens": 100, "output_tokens": 2, "total_tokens": 999},
        {"input_tokens": 100, "output_tokens": 2, "total_tokens": 102, "input_token_details": {"cache_read": 101}},
    ],
)
def test_malformed_usage_returns_none(usage: object) -> None:
    assert usage_from_message(_message(usage), "gpt-4o-mini") is None


def test_openai_compatible_usage_is_supported_without_content() -> None:
    result = usage_from_message(
        _message(
            response_metadata={
                "token_usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 4,
                    "total_tokens": 14,
                    "prompt_tokens_details": {"cached_tokens": 0},
                },
                "provider_payload": "must-not-be-returned",
            }
        ),
        "gpt-4o-mini",
    )
    assert result is not None and result.total_tokens == 14
    assert "payload" not in repr(result)


def test_unknown_model_keeps_tokens_and_omits_cost() -> None:
    result = usage_from_message(
        _message({"input_tokens": 10, "output_tokens": 4, "total_tokens": 14}),
        "unpriced-model",
    )
    assert result is not None and result.total_tokens == 14 and result.cost_usd is None
