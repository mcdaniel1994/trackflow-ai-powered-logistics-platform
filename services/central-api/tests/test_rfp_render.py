"""Deterministic Markdown rendering of a finalized RFP proposal (final-polish 2.2)."""

from __future__ import annotations

from datetime import UTC, datetime

from central_api.domains.rfp.models import RfpDepartmentSection, RfpFinalDocument, RfpTicket
from central_api.domains.rfp.pdf import build_proposal_html
from central_api.domains.rfp.render import render_final_document


def _ticket() -> RfpTicket:
    return RfpTicket(
        id="11111111-1111-4111-8111-111111111111",
        rfp_id="RFP-ABC123",
        status="done",
        owner_user_uuid="owner",
        client_name="Luna Retail",
        client_country="US",
        currency="USD",
        monthly_volume=5000,
        deadline_days=20,
    )


def _document(sections: dict[str, str]) -> RfpFinalDocument:
    return RfpFinalDocument(
        ticket_id="11111111-1111-4111-8111-111111111111",
        sections=sections,
        currency="USD",
        generated_at=datetime(2026, 8, 19, 12, 0, tzinfo=UTC),
    )


def _section(department_id: str, *, approver: str | None = None) -> RfpDepartmentSection:
    return RfpDepartmentSection(
        ticket_id="11111111-1111-4111-8111-111111111111",
        department_id=department_id,
        approval_status="approved",
        draft_content=f"Draft for {department_id}",
        approver=approver,
        approved_at=datetime(2026, 8, 19, 11, 0, tzinfo=UTC) if approver else None,
    )


def test_render_includes_heading_metadata_and_sections() -> None:
    document = _document({"lastmile": "Last-mile section body.", "warehouse": "Warehouse section body."})
    sections = [_section("warehouse", approver="ana@trackflow.local"), _section("lastmile")]

    markdown = render_final_document(_ticket(), document, sections)

    assert markdown.startswith("# RFP Proposal — Luna Retail")
    assert "| Currency | USD |" in markdown
    assert "| Monthly volume | 5,000 |" in markdown
    assert f"| Ticket | {_ticket().id} |" in markdown
    assert "## Warehouse & Storage" in markdown
    assert "Warehouse section body." in markdown
    assert "Approved by ana@trackflow.local" in markdown
    assert "reviewed and approved by a human account manager" in markdown


def test_render_department_order_is_fixed_and_deterministic() -> None:
    # Stored dict is in reverse order; the renderer must emit the canonical order regardless.
    document = _document({"reverse": "R", "lastmile": "L", "warehouse": "W"})
    sections = [_section("warehouse"), _section("lastmile"), _section("reverse")]

    markdown = render_final_document(_ticket(), document, sections)

    warehouse = markdown.index("## Warehouse & Storage")
    lastmile = markdown.index("## Last-Mile Delivery")
    reverse = markdown.index("## Reverse Logistics")
    assert warehouse < lastmile < reverse
    # Repeated renders are byte-identical.
    assert render_final_document(_ticket(), document, sections) == markdown


def test_build_proposal_html_is_branded_and_renders_markdown() -> None:
    document = _document(
        {"warehouse": "## Storage\nWe offer **98% on-time**.\n\n| Volume | Discount |\n| --- | --- |\n| 1000+ | 5% |"}
    )
    html = build_proposal_html(_ticket(), document, [_section("warehouse")])

    assert "Track<span>" in html  # branded wordmark
    assert "Luna Retail" in html  # prepared-for client
    assert "Commercial Proposal" in html
    assert "Warehouse &amp; Storage" in html  # ordered department heading
    assert "<strong>98% on-time</strong>" in html  # bold markdown
    assert "<table>" in html and "<th>Volume</th>" in html  # discount-tier table rendered
    assert "Los Angeles, USA" in html  # professional footer


def test_build_proposal_html_escapes_section_content() -> None:
    document = _document({"warehouse": "<script>alert(1)</script>"})
    html = build_proposal_html(_ticket(), document, [_section("warehouse")])
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_markdown_carries_the_deterministic_commercial_summary() -> None:
    """A proposal is read as a quote; it must state a price, and the same price
    every time it is rendered."""
    markdown = render_final_document(_ticket(), _document({"warehouse": "Draft"}), [])

    assert "## Commercial Summary" in markdown
    assert "| Service | Volume | Unit price | Monthly cost |" in markdown
    # 5,000 shipments at $6.40 for a US ticket.
    assert "$32,000.00" in markdown
    assert "not a binding quotation" in markdown
    # The summary precedes the department sections.
    assert markdown.index("## Commercial Summary") < markdown.index("## Warehouse & Storage")


def test_pdf_and_markdown_quote_the_same_figures() -> None:
    """Two independent renderers reading one ticket must never disagree on price."""
    ticket, document = _ticket(), _document({"warehouse": "Draft"})
    markdown = render_final_document(ticket, document, [])
    rendered_html = build_proposal_html(ticket, document, [])

    assert "Commercial Summary" in rendered_html
    for amount in ("$32,000.00", "$1,170.00", "$1,080.00"):
        assert amount in markdown
        assert amount in rendered_html


def test_commercial_summary_follows_the_document_currency() -> None:
    ticket = _ticket()
    ticket.client_country = "ES"
    document = _document({"warehouse": "Draft"})
    document.currency = "EUR"

    markdown = render_final_document(ticket, document, [])
    assert "€29,000.00" in markdown
    assert "$" not in markdown
