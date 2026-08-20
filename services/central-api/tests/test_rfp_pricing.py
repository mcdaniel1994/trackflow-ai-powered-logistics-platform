"""Deterministic RFP cost estimate: arithmetic, currency, tiers, and KB sync.

These figures reach a client as a quotation, so the tests assert exact amounts
rather than ranges. The KB-sync test is the important one: it is what stops the
rate card in code drifting away from the policy document the RAG layer grounds
prose in.
"""

from __future__ import annotations

import re
from decimal import Decimal
from pathlib import Path

import pytest

from central_api.domains.rfp.pricing import (
    CUBIC_METERS_PER_ORDER,
    DEFAULT_CURRENCY,
    FALLBACK_MONTHLY_VOLUME,
    LAST_MILE_STANDARD,
    RETURN_RATE,
    RETURNS_PROCESSING,
    STORAGE_PER_CUBIC_METER,
    build_cost_breakdown,
    cost_summary_markdown,
    discount_for_volume,
    resolve_currency,
)

KB_ROOT = Path(__file__).resolve().parents[3] / "docs" / "company-knowledge-base"


def _flattened(name: str) -> str:
    """Read a KB document as one whitespace-normalised line.

    These are hand-written prose documents that get reflowed by editors, so a
    rate must be findable regardless of where the line happens to break.
    """
    return re.sub(r"\s+", " ", (KB_ROOT / name).read_text(encoding="utf-8"))


def test_line_arithmetic_is_exact_for_a_known_volume() -> None:
    breakdown = build_cost_breakdown("USD", 1_000)
    last_mile, returns, storage = breakdown.lines

    # 1,000 shipments at 6.40
    assert last_mile.line_total == Decimal("6400.00")
    # 6% of 1,000 = 60 units at 3.90
    assert returns.quantity == Decimal("60")
    assert returns.line_total == Decimal("234.00")
    # 1,000 * 0.012 = 12 m3 at 18.00
    assert storage.quantity == Decimal("12.00")
    assert storage.line_total == Decimal("216.00")

    assert breakdown.subtotal == Decimal("6850.00")
    # 5% tier applies to last-mile + returns only, never to storage.
    assert breakdown.discount_amount == Decimal("331.70")
    assert breakdown.total == Decimal("6518.30")
    assert breakdown.annual_total == Decimal("78219.60")


def test_storage_is_excluded_from_the_discount() -> None:
    """Storage discounts require account-management approval, so the published
    tier table must never appear to grant one."""
    breakdown = build_cost_breakdown("USD", 20_000)
    _last_mile, _returns, storage = breakdown.lines

    discountable = breakdown.subtotal - storage.line_total
    assert breakdown.discount_amount == (discountable * breakdown.discount_rate).quantize(
        Decimal("0.01")
    )


@pytest.mark.parametrize(
    ("volume", "rate"),
    [
        (0, Decimal("0.00")),
        (999, Decimal("0.00")),
        (1_000, Decimal("0.05")),
        (4_999, Decimal("0.05")),
        (5_000, Decimal("0.08")),
        (19_999, Decimal("0.08")),
        (20_000, Decimal("0.12")),
        (250_000, Decimal("0.12")),
    ],
)
def test_discount_tier_boundaries(volume: int, rate: Decimal) -> None:
    assert discount_for_volume(volume)[0] == rate


def test_currency_selects_the_matching_rate_card() -> None:
    usd = build_cost_breakdown("USD", 2_000)
    eur = build_cost_breakdown("EUR", 2_000)

    assert usd.symbol == "$"
    assert eur.symbol == "€"
    assert usd.lines[0].unit_price == LAST_MILE_STANDARD["USD"]
    assert eur.lines[0].unit_price == LAST_MILE_STANDARD["EUR"]
    assert eur.total < usd.total


@pytest.mark.parametrize("currency", [None, "", "GBP", "usd"])
def test_unknown_currency_falls_back_exactly_as_finalize_does(currency: str | None) -> None:
    """approval.py finalizes with `ticket.currency or 'USD'`; this must agree, or
    the document header and the cost table could disagree."""
    assert resolve_currency(currency) == DEFAULT_CURRENCY


def test_missing_volume_is_labelled_as_illustrative() -> None:
    """An RFP that never states a volume still gets a table, but the reader must
    be told the number was assumed."""
    breakdown = build_cost_breakdown("USD", None)

    assert breakdown.volume_assumed is True
    assert breakdown.monthly_volume == FALLBACK_MONTHLY_VOLUME
    assert any("did not state a monthly volume" in item for item in breakdown.assumptions)

    stated = build_cost_breakdown("USD", 3_000)
    assert stated.volume_assumed is False
    assert not any("did not state" in item for item in stated.assumptions)


def test_markdown_is_a_pipe_table_and_states_its_assumptions() -> None:
    """pdf.py's Markdown converter supports pipe tables and little else, so the
    table must stay in that syntax to survive into the PDF."""
    markdown = cost_summary_markdown(build_cost_breakdown("EUR", 5_000))

    assert "| Service | Volume | Unit price | Monthly cost |" in markdown
    assert "| --- | --- | --- | --- |" in markdown
    assert "€" in markdown and "$" not in markdown
    assert "**Assumptions**" in markdown
    assert "not a binding quotation" in markdown
    assert "8%" in markdown


def test_output_is_byte_stable() -> None:
    """The final document asserts byte stability across repeated renders."""
    first = cost_summary_markdown(build_cost_breakdown("USD", 7_500))
    second = cost_summary_markdown(build_cost_breakdown("USD", 7_500))
    assert first == second


def test_rates_match_the_knowledge_base_document() -> None:
    """The KB document is what retrieval grounds prose in; the constants are what
    the client-facing table is built from. If they drift, the proposal contradicts
    itself."""
    service = _flattened("trackflow-service-pricing.en.md")
    storage = _flattened("trackflow-storage-pricing.en.md")

    assert f"{LAST_MILE_STANDARD['USD']} USD per shipment" in service
    assert f"{LAST_MILE_STANDARD['EUR']} EUR per shipment" in service
    assert f"{RETURNS_PROCESSING['USD']} USD per unit" in service
    assert f"{RETURNS_PROCESSING['EUR']} EUR per unit" in service
    assert f"{CUBIC_METERS_PER_ORDER} cubic meters" in service
    assert f"{RETURN_RATE:.0%} of monthly orders" in service

    assert f"{STORAGE_PER_CUBIC_METER['USD']:.0f} USD per cubic meter" in storage
    assert f"{STORAGE_PER_CUBIC_METER['EUR']:.0f} EUR per cubic meter" in storage


def test_discount_tiers_match_the_knowledge_base_document() -> None:
    service = _flattened("trackflow-service-pricing.en.md")

    assert "5% discount tier" in service
    assert "8% discount tier" in service
    assert "12% discount tier" in service
    # The tier table must not appear to authorise a storage discount.
    assert "Storage discounts are not covered by this" in service
