"""PDF→Markdown conversion (pdfminer mocked; no real PDF parsing)."""

from __future__ import annotations

import pytest

from central_api.domains.rfp import document
from central_api.domains.rfp.document import DocumentError, pdf_to_markdown


def test_empty_bytes_rejected() -> None:
    with pytest.raises(DocumentError):
        pdf_to_markdown(b"")


def test_oversized_rejected() -> None:
    with pytest.raises(DocumentError):
        pdf_to_markdown(b"x" * (document.MAX_PDF_BYTES + 1))


def test_unreadable_pdf_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(_stream: object) -> str:
        raise ValueError("not a pdf")

    monkeypatch.setattr("pdfminer.high_level.extract_text", boom)
    with pytest.raises(DocumentError):
        pdf_to_markdown(b"%PDF-1.4 broken")


def test_no_text_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pdfminer.high_level.extract_text", lambda _s: "   \x0c  ")
    with pytest.raises(DocumentError):
        pdf_to_markdown(b"%PDF-1.4")


def test_converts_and_normalizes_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pdfminer.high_level.extract_text", lambda _s: "Title\r\n\n\n\nBody   \nline\x0cPage 2")
    markdown = pdf_to_markdown(b"%PDF-1.4")
    assert "Title" in markdown and "Body" in markdown and "Page 2" in markdown
    assert "\n\n\n" not in markdown  # collapsed blank runs
    assert "   \n" not in markdown  # trailing whitespace stripped
