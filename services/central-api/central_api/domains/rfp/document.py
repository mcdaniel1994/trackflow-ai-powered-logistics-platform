"""PDF → Markdown conversion for RFP intake.

RFPs arrive as PDFs; converting to Markdown before any agent processes them cuts token cost and gives
the agents clean text. We use ``pdfminer.six`` (the same engine MarkItDown wraps for PDFs) directly,
to avoid a heavy native ML runtime we do not need. The raw PDF bytes are converted here and then
discarded by the caller (owner decision): only the resulting Markdown is persisted.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB upload ceiling
_MULTI_BLANK_RE = re.compile(r"\n{3,}")
_TRAILING_WS_RE = re.compile(r"[ \t]+\n")


@dataclass
class DocumentError(Exception):
    """Raised when an uploaded document cannot be accepted or converted."""

    detail: str


def _normalize(text: str) -> str:
    """Collapse the noisy whitespace pdfminer emits into clean Markdown-ready paragraphs."""
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n\n")
    text = _TRAILING_WS_RE.sub("\n", text)
    text = _MULTI_BLANK_RE.sub("\n\n", text)
    return text.strip()


def pdf_to_markdown(data: bytes) -> str:
    """Extract text from PDF bytes and return normalized Markdown-ready text.

    Raises ``DocumentError`` for empty, oversized, or unreadable input so the caller can fail the
    ticket explicitly rather than persist an empty document.
    """
    if not data:
        raise DocumentError("The uploaded file is empty.")
    if len(data) > MAX_PDF_BYTES:
        raise DocumentError("The uploaded PDF exceeds the 10 MB limit.")

    try:
        from pdfminer.high_level import extract_text

        text = extract_text(io.BytesIO(data))
    except Exception as exc:  # pdfminer raises a variety of parse errors on malformed input
        raise DocumentError("The uploaded file could not be read as a PDF.") from exc

    markdown = _normalize(text or "")
    if not markdown:
        raise DocumentError("No readable text was found in the PDF.")
    return markdown
