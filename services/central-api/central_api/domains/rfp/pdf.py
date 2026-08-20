"""Render a finalized RFP proposal to a professional, branded PDF (final-polish).

Deterministic HTML build + WeasyPrint render; no LLM and no persistence (the PDF is produced on the
fly for the download response and never stored — consistent with the raw-bytes-never-persisted rule).
Section drafts are Markdown, converted by a small, HTML-escaping converter so draft text can never
inject markup into the document.
"""

from __future__ import annotations

import html
import re
import sys
from datetime import UTC
from typing import cast

from .models import RfpDepartmentSection, RfpFinalDocument, RfpTicket
from .render import _DEPARTMENT_NAMES, _ordered_departments  # reuse the canonical order + names

_COUNTRY_NAMES = {"US": "United States", "ES": "Spain"}


def _inline(text: str) -> str:
    escaped = html.escape(text)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(^|[^*])\*([^*]+)\*(?!\*)", r"\1<em>\2</em>", escaped)
    return escaped


def _cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _render_table(rows: list[str]) -> str:
    header = "".join(f"<th>{_inline(cell)}</th>" for cell in _cells(rows[0]))
    body = "".join(
        "<tr>" + "".join(f"<td>{_inline(cell)}</td>" for cell in _cells(row)) + "</tr>"
        for row in rows[2:]  # skip the |---| separator row
    )
    return f"<table><tr>{header}</tr>{body}</table>"


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    list_type: str | None = None
    list_items: list[str] = []
    table: list[str] = []

    def flush_list() -> None:
        nonlocal list_type, list_items
        if list_type:
            items = "".join(f"<li>{item}</li>" for item in list_items)
            out.append(f"<{list_type}>{items}</{list_type}>")
            list_type, list_items = None, []

    def flush_table() -> None:
        nonlocal table
        if len(table) >= 2:
            out.append(_render_table(table))
        table = []

    for raw in lines:
        line = raw.rstrip()
        if re.match(r"^\s*\|.*\|\s*$", line):
            flush_list()
            table.append(line.strip())
            continue
        flush_table()
        if not line.strip():
            flush_list()
            continue
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            flush_list()
            level = min(len(heading.group(1)) + 2, 6)
            out.append(f"<h{level}>{_inline(heading.group(2))}</h{level}>")
            continue
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet:
            if list_type != "ul":
                flush_list()
                list_type = "ul"
            list_items.append(_inline(bullet.group(1)))
            continue
        numbered = re.match(r"^\s*\d+\.\s+(.*)$", line)
        if numbered:
            if list_type != "ol":
                flush_list()
                list_type = "ol"
            list_items.append(_inline(numbered.group(1)))
            continue
        flush_list()
        out.append(f"<p>{_inline(line)}</p>")

    flush_list()
    flush_table()
    return "\n".join(out)


_STYLE = """
  @page { size: A4; margin: 18mm 16mm 22mm; }
  * { box-sizing: border-box; }
  body { font-family: "DejaVu Sans", "Helvetica", sans-serif; color: #243b53; font-size: 10.5pt;
    line-height: 1.5; margin: 0; }
  header.brand { display: flex; justify-content: space-between; align-items: flex-start;
    border-bottom: 3px solid #1f3a5f; padding-bottom: 10px; }
  .wordmark { font-size: 22pt; font-weight: 800; color: #1f3a5f; }
  .wordmark span { color: #e2703a; }
  .tagline { color: #627d98; font-size: 8.5pt; }
  .doc-meta { text-align: right; font-size: 8.5pt; color: #627d98; }
  h1.title { font-size: 17pt; color: #1f3a5f; margin: 22px 0 2px; }
  .prepared { color: #627d98; margin: 0 0 16px; }
  .summary { border: 1px solid #e4e9f0; border-radius: 8px; padding: 12px 16px; margin-bottom: 20px; }
  .summary table { width: 100%; border-collapse: collapse; }
  .summary td { padding: 3px 8px; font-size: 9.5pt; }
  .summary .k { color: #627d98; text-transform: uppercase; letter-spacing: .04em; font-size: 8pt;
    font-weight: 700; width: 22%; }
  section.dept { margin: 18px 0; }
  section.dept h2 { color: #1f3a5f; font-size: 13pt; border-bottom: 1px solid #e4e9f0;
    padding-bottom: 4px; margin: 0 0 8px; }
  h3, h4 { color: #243b53; font-size: 11pt; margin: 12px 0 4px; }
  p { margin: 6px 0; }
  ul, ol { margin: 6px 0 6px 18px; padding: 0; }
  li { margin: 2px 0; }
  table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 9.5pt; }
  th, td { border: 1px solid #e4e9f0; padding: 5px 9px; text-align: left; }
  th { background: #f0f4f9; color: #1f3a5f; font-weight: 700; }
  .approved { margin-top: 26px; padding: 12px 16px; background: #f2f8f4; border: 1px solid #cfe6d6;
    border-radius: 8px; color: #2f6b46; font-size: 9.5pt; }
  footer.brand { border-top: 1px solid #e4e9f0; padding-top: 8px; margin-top: 26px;
    font-size: 8pt; color: #627d98; display: flex; justify-content: space-between; }
"""


def build_proposal_html(
    ticket: RfpTicket, document: RfpFinalDocument, sections: list[RfpDepartmentSection]
) -> str:
    generated = document.generated_at.astimezone(UTC)
    date_label = generated.strftime("%B %-d, %Y")
    client = html.escape(ticket.client_name or ticket.rfp_id)
    country = _COUNTRY_NAMES.get(ticket.client_country or "", ticket.client_country or "—")
    stored = document.sections if isinstance(document.sections, dict) else {}
    volume = f"{ticket.monthly_volume:,}" if ticket.monthly_volume is not None else "—"
    deadline = f"{ticket.deadline_days} days" if ticket.deadline_days is not None else "—"

    body = "\n".join(
        f'<section class="dept"><h2>{html.escape(_DEPARTMENT_NAMES.get(dept, dept))}</h2>'
        f"{_markdown_to_html(str(stored.get(dept) or ''))}</section>"
        for dept in _ordered_departments(list(stored.keys()))
    )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8" />
<title>TrackFlow Proposal — {client}</title><style>{_STYLE}</style></head><body>
  <header class="brand">
    <div><div class="wordmark">Track<span>Flow</span></div>
      <div class="tagline">Warehouse Management &amp; Last-Mile Logistics</div></div>
    <div class="doc-meta"><div><strong>Commercial Proposal</strong></div>
      <div>{date_label}</div><div>Ref: {html.escape(ticket.rfp_id)}</div></div>
  </header>
  <h1 class="title">Logistics Services Proposal</h1>
  <p class="prepared">Prepared for <strong>{client}</strong></p>
  <div class="summary"><table>
    <tr><td class="k">Client</td><td>{client}</td><td class="k">Country</td><td>{html.escape(country)}</td></tr>
    <tr><td class="k">Currency</td><td>{html.escape(document.currency)}</td>
        <td class="k">Monthly volume</td><td>{volume}</td></tr>
    <tr><td class="k">Requested deadline</td><td>{deadline}</td>
        <td class="k">Prepared on</td><td>{date_label}</td></tr>
  </table></div>
  {body}
  <div class="approved">Every section of this proposal was reviewed and approved by a TrackFlow
    account manager.</div>
  <footer class="brand"><span>TrackFlow &middot; Los Angeles, USA &nbsp;&middot;&nbsp; Zaragoza, Spain</span>
    <span>hello@trackflow.com &nbsp;&middot;&nbsp; trackflow.com</span></footer>
</body></html>"""


def _ensure_native_libs_discoverable() -> None:
    """Help WeasyPrint find Homebrew's Pango/cairo on macOS dev machines.

    macOS SIP strips ``DYLD_*`` env vars, and ``ctypes.util.find_library`` does not search Homebrew's
    ``/opt/homebrew/lib``. This patches ``find_library`` to fall back to the Homebrew lib dirs. On Linux
    (the production container) the libraries are installed system-wide, so the original lookup already
    succeeds and this fallback never runs.
    """
    if sys.platform != "darwin":
        return
    import ctypes.util
    import glob
    import os

    if getattr(ctypes.util.find_library, "_trackflow_patched", False):
        return
    original = ctypes.util.find_library
    brew_dirs = ["/opt/homebrew/lib", "/usr/local/lib"]

    def find_library(name: str) -> str | None:
        found = original(name)
        if found:
            return found
        for directory in brew_dirs:
            for candidate in (f"lib{name}.dylib", f"lib{name}.0.dylib"):
                path = os.path.join(directory, candidate)
                if os.path.exists(path):
                    return path
            hits = sorted(glob.glob(os.path.join(directory, f"lib{name}*.dylib")))
            if hits:
                return hits[0]
        return None

    find_library._trackflow_patched = True  # type: ignore[attr-defined]
    ctypes.util.find_library = find_library


def render_final_document_pdf(
    ticket: RfpTicket, document: RfpFinalDocument, sections: list[RfpDepartmentSection]
) -> bytes:
    """Render the approved proposal to PDF bytes (WeasyPrint). Never persisted."""
    _ensure_native_libs_discoverable()
    from weasyprint import HTML  # imported lazily so the module loads without the native libs

    # WeasyPrint ships no type information, so `write_pdf()` is Any; the cast keeps
    # this function's declared return type meaningful to callers.
    return cast(bytes, HTML(string=build_proposal_html(ticket, document, sections)).write_pdf())
