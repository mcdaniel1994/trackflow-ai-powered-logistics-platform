"""Deterministic Markdown rendering of a completed RFP proposal (Engagement 9 / final-polish 2.2).

Pure function, no LLM and no I/O: it turns a finalized ticket, its stored final document, and its
department section rows into one Markdown document. Section drafts are already Markdown, so they are
emitted verbatim. Department order is a fixed constant (never dict-insertion or DB row order) so a
download is byte-stable across repeated calls for the same ticket.
"""

from __future__ import annotations

from .models import RfpDepartmentSection, RfpFinalDocument, RfpTicket
from .pricing import build_cost_breakdown, cost_summary_markdown

# Fixed presentation order and human-readable names. Mirrors models.DEPARTMENT_VALUES but is declared
# explicitly here so the rendered order is a documented decision, not an incidental one.
_DEPARTMENT_ORDER: tuple[str, ...] = ("warehouse", "lastmile", "reverse")
_DEPARTMENT_NAMES: dict[str, str] = {
    "warehouse": "Warehouse & Storage",
    "lastmile": "Last-Mile Delivery",
    "reverse": "Reverse Logistics",
}


def _department_name(department_id: str) -> str:
    return _DEPARTMENT_NAMES.get(department_id, department_id.replace("_", " ").title())


def _ordered_departments(section_ids: list[str]) -> list[str]:
    """Canonical order first, then any unexpected department id in a stable (sorted) tail."""
    known = [dept for dept in _DEPARTMENT_ORDER if dept in section_ids]
    extra = sorted(dept for dept in section_ids if dept not in _DEPARTMENT_ORDER)
    return known + extra


def render_final_document(
    ticket: RfpTicket,
    document: RfpFinalDocument,
    sections: list[RfpDepartmentSection],
) -> str:
    """Render the consolidated, human-approved proposal as Markdown."""
    heading_subject = ticket.client_name or ticket.rfp_id
    generated = document.generated_at.astimezone().isoformat()

    lines: list[str] = [f"# RFP Proposal — {heading_subject}", ""]

    # Metadata block.
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Client | {ticket.client_name or '—'} |")
    lines.append(f"| Client country | {ticket.client_country or '—'} |")
    lines.append(f"| Currency | {document.currency} |")
    volume = f"{ticket.monthly_volume:,}" if ticket.monthly_volume is not None else "—"
    lines.append(f"| Monthly volume | {volume} |")
    deadline = f"{ticket.deadline_days} days" if ticket.deadline_days is not None else "—"
    lines.append(f"| Deadline | {deadline} |")
    lines.append(f"| Generated | {generated} |")
    lines.append(f"| Ticket | {ticket.id} |")
    lines.append("")

    # Deterministic commercial estimate. Computed rather than generated, so the
    # figures cannot drift between renders or between the Markdown and the PDF.
    breakdown = build_cost_breakdown(document.currency, ticket.monthly_volume)
    lines.append("## Commercial Summary")
    lines.append("")
    lines.append(cost_summary_markdown(breakdown).rstrip())
    lines.append("")

    by_id = {section.department_id: section for section in sections}
    stored = document.sections if isinstance(document.sections, dict) else {}

    for department_id in _ordered_departments(list(stored.keys())):
        section = by_id.get(department_id)
        content = str(stored.get(department_id, "")).strip()
        lines.append(f"## {_department_name(department_id)}")
        lines.append("")
        lines.append(content or "_No content was recorded for this section._")
        lines.append("")
        if section is not None and section.approver:
            approved_at = section.approved_at.astimezone().isoformat() if section.approved_at else "—"
            lines.append(f"_Approved by {section.approver} on {approved_at}._")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("Every section in this proposal was reviewed and approved by a human account manager.")
    lines.append("")

    return "\n".join(lines)
