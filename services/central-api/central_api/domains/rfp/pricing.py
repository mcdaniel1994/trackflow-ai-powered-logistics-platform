"""Deterministic cost estimate for an RFP proposal.

Proposals previously quoted no price at all, which is conspicuous in a document
presented as a commercial offer. The figures here are computed rather than
generated: an LLM asked to price a proposal will produce different numbers on
every run and cannot be held to a rate card, which is not acceptable in a
document a client reads as a quote.

**Every rate below mirrors `docs/company-knowledge-base/trackflow-service-pricing.en.md`
and `trackflow-storage-pricing.en.md`.** Those documents are the human-readable
source of truth and what the retrieval layer grounds prose in;
`tests/test_rfp_pricing.py` asserts the two cannot drift apart.

The module is pure: no I/O, no database, no LLM. Both renderers call it, so the
Markdown and the PDF cannot disagree, and repeated renders stay byte-identical.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

# Per outbound shipment, standard service. Proposals assume standard unless the
# client asks otherwise.
LAST_MILE_STANDARD: dict[str, Decimal] = {
    "USD": Decimal("6.40"),
    "EUR": Decimal("5.80"),
}

# Per returned unit received and processed. Excludes return shipping.
RETURNS_PROCESSING: dict[str, Decimal] = {
    "USD": Decimal("3.90"),
    "EUR": Decimal("3.50"),
}

# Per cubic meter per month: Los Angeles quoted in USD, Zaragoza in EUR.
STORAGE_PER_CUBIC_METER: dict[str, Decimal] = {
    "USD": Decimal("18.00"),
    "EUR": Decimal("16.00"),
}

# Planning assumptions, stated in the proposal wherever they are used. Neither is
# a measurement, and both are labelled as estimates in the rendered output.
CUBIC_METERS_PER_ORDER = Decimal("0.012")
RETURN_RATE = Decimal("0.06")

# Applied to the last-mile + returns subtotal only. Storage discounts are
# deliberately excluded: they require Miguel Torres's approval and an account
# manager cannot grant them, so this table must never appear to offer one.
DISCOUNT_TIERS: tuple[tuple[int, Decimal, str], ...] = (
    (20_000, Decimal("0.12"), "20,000+ orders / month"),
    (5_000, Decimal("0.08"), "5,000-19,999 orders / month"),
    (1_000, Decimal("0.05"), "1,000-4,999 orders / month"),
    (0, Decimal("0.00"), "Up to 999 orders / month"),
)

CURRENCY_SYMBOLS: dict[str, str] = {"USD": "$", "EUR": "€"}
DEFAULT_CURRENCY = "USD"

# Volume used when the uploaded RFP never stated one, so a proposal still carries
# an illustrative figure instead of an empty table.
FALLBACK_MONTHLY_VOLUME = 1_000


@dataclass(frozen=True)
class CostLine:
    """One priced row of the estimate."""

    label: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    line_total: Decimal


@dataclass(frozen=True)
class CostBreakdown:
    """A complete monthly estimate, ready to render."""

    currency: str
    symbol: str
    monthly_volume: int
    volume_assumed: bool
    lines: tuple[CostLine, ...]
    subtotal: Decimal
    discount_rate: Decimal
    discount_tier_label: str
    discount_amount: Decimal
    total: Decimal
    assumptions: tuple[str, ...]

    @property
    def annual_total(self) -> Decimal:
        return _money(self.total * 12)


def _money(value: Decimal) -> Decimal:
    """Round to cents, half-up, as a quoted price would be."""
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resolve_currency(currency: str | None) -> str:
    """Fall back exactly as `approval.py` does when a ticket has no currency."""
    return currency if currency in CURRENCY_SYMBOLS else DEFAULT_CURRENCY


def discount_for_volume(monthly_volume: int) -> tuple[Decimal, str]:
    """Return the published tier for a volume. Tiers are ordered high to low."""
    for threshold, rate, label in DISCOUNT_TIERS:
        if monthly_volume >= threshold:
            return rate, label
    return Decimal("0.00"), DISCOUNT_TIERS[-1][2]


def build_cost_breakdown(
    currency: str | None,
    monthly_volume: int | None,
) -> CostBreakdown:
    """Compute the monthly estimate for a ticket.

    Currency is derived upstream from the client's country and is never taken
    from user input; this only normalises a missing value.
    """
    code = resolve_currency(currency)
    symbol = CURRENCY_SYMBOLS[code]
    volume_assumed = monthly_volume is None or monthly_volume <= 0
    volume = FALLBACK_MONTHLY_VOLUME if volume_assumed else int(monthly_volume or 0)
    orders = Decimal(volume)

    returned_units = (orders * RETURN_RATE).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    cubic_meters = (orders * CUBIC_METERS_PER_ORDER).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    last_mile = CostLine(
        label="Last-mile delivery (standard)",
        quantity=orders,
        unit="shipments / month",
        unit_price=LAST_MILE_STANDARD[code],
        line_total=_money(orders * LAST_MILE_STANDARD[code]),
    )
    returns = CostLine(
        label="Returns processing",
        quantity=returned_units,
        unit="units / month",
        unit_price=RETURNS_PROCESSING[code],
        line_total=_money(returned_units * RETURNS_PROCESSING[code]),
    )
    storage = CostLine(
        label="Storage (estimated)",
        quantity=cubic_meters,
        unit="m³ / month",
        unit_price=STORAGE_PER_CUBIC_METER[code],
        line_total=_money(cubic_meters * STORAGE_PER_CUBIC_METER[code]),
    )

    # The tier applies to fulfilment only; storage is added back after it.
    discountable = last_mile.line_total + returns.line_total
    rate, tier_label = discount_for_volume(volume)
    discount_amount = _money(discountable * rate)
    subtotal = _money(discountable + storage.line_total)
    total = _money(subtotal - discount_amount)

    assumptions = [
        f"Storage estimated at {CUBIC_METERS_PER_ORDER} m³ per monthly order; to be "
        "confirmed once real product dimensions are known.",
        f"Returns estimated at {RETURN_RATE:.0%} of monthly orders.",
        "Standard delivery service assumed for all shipments.",
        "Volume discount applies to last-mile and returns processing only. Storage "
        "discounts require account-management approval and are not included here.",
    ]
    if volume_assumed:
        assumptions.insert(
            0,
            f"The RFP did not state a monthly volume; {FALLBACK_MONTHLY_VOLUME:,} orders "
            "per month is used as an illustrative figure.",
        )

    return CostBreakdown(
        currency=code,
        symbol=symbol,
        monthly_volume=volume,
        volume_assumed=volume_assumed,
        lines=(last_mile, returns, storage),
        subtotal=subtotal,
        discount_rate=rate,
        discount_tier_label=tier_label,
        discount_amount=discount_amount,
        total=total,
        assumptions=tuple(assumptions),
    )


def format_amount(breakdown: CostBreakdown, value: Decimal) -> str:
    """Render a money value in the proposal's currency."""
    return f"{breakdown.symbol}{value:,.2f}"


def cost_summary_markdown(breakdown: CostBreakdown) -> str:
    """Render the estimate as a Markdown pipe table plus assumptions.

    Pipe tables are the richest construct `pdf.py:_markdown_to_html` supports, so
    this renders correctly in both the Markdown download and the PDF.
    """
    rows = [
        "| Service | Volume | Unit price | Monthly cost |",
        "| --- | --- | --- | --- |",
    ]
    for line in breakdown.lines:
        quantity = f"{line.quantity:,.2f}" if line.unit.startswith("m³") else f"{line.quantity:,.0f}"
        rows.append(
            f"| {line.label} | {quantity} {line.unit} | "
            f"{format_amount(breakdown, line.unit_price)} | "
            f"{format_amount(breakdown, line.line_total)} |"
        )
    rows.append(f"| **Subtotal** |  |  | **{format_amount(breakdown, breakdown.subtotal)}** |")
    rows.append(
        f"| Volume discount tier ({breakdown.discount_tier_label}) |  | "
        f"{breakdown.discount_rate:.0%} | "
        f"-{format_amount(breakdown, breakdown.discount_amount)} |"
    )
    rows.append(
        f"| **Estimated monthly total** |  |  | **{format_amount(breakdown, breakdown.total)}** |"
    )

    assumptions = "\n".join(f"- {item}" for item in breakdown.assumptions)
    return (
        "\n".join(rows)
        + f"\n\nEstimated annual total: **{format_amount(breakdown, breakdown.annual_total)}** "
        f"({breakdown.currency}).\n\n**Assumptions**\n\n"
        + assumptions
        + "\n\nAll figures are a draft estimate for review by the account manager and are "
        "not a binding quotation.\n"
    )
