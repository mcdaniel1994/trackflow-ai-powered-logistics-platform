"""Pure chunking transforms for the RAG knowledge base (Engagement 7).

This module has a single responsibility: turn a company knowledge-base document into
self-contained semantic chunks. It performs no network or vector-store I/O — indexing
lives in ``pipelines.rag.setup``. Keeping chunking pure makes it deterministic and unit
testable without a live Qdrant or embeddings provider.

Chunking strategy (documented in ``docs/rag/rag-design.md``):

* Split the document body on blank lines into paragraph blocks.
* A bullet or numbered list is glued to the paragraph immediately above it, so a rule and
  its conditions are never separated (e.g. "Standard shipping:" keeps its "3 to 5 business
  days" bullet).
* A short intro paragraph that ends in a colon is glued to the block that follows it, so a
  section lead-in is never left stranded as its own fragment.

The corpus documents are flat (a single H1, no subsections), so ``section`` defaults to the
document title and is refined to ``"Title — Label"`` when a chunk opens with a short
``Label:`` lead so retrieval hits stay traceable to a meaningful part of the source.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field

# Fixed namespace so point IDs are stable across re-indexing runs (idempotency).
POINT_ID_NAMESPACE = uuid.UUID("6f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b")

COMPANY = "trackflow"
LANGUAGE = "en"

_LIST_ITEM = re.compile(r"^\s*(?:[-*+]\s|\d+[.)]\s)")
_LABEL_LEAD = re.compile(r"^([A-Z][^.:\n]{2,44}):")


@dataclass(frozen=True)
class Chunk:
    """A self-contained passage plus the metadata stored alongside its vector."""

    source_document: str
    section: str
    chunk_index: int
    text: str
    company: str = COMPANY
    language: str = LANGUAGE

    @property
    def point_id(self) -> str:
        """Deterministic Qdrant point ID: identical input always upserts in place."""
        return str(uuid.uuid5(POINT_ID_NAMESPACE, f"{self.source_document}:{self.chunk_index}"))

    def payload(self) -> dict[str, object]:
        """Return the Qdrant payload using the exact field names from context.md."""
        return {
            "company": self.company,
            "source_document": self.source_document,
            "section": self.section,
            "language": self.language,
            "chunk_index": self.chunk_index,
            "text": self.text,
        }


@dataclass
class _Block:
    text: str
    is_list: bool = field(default=False)


def source_document_slug(filename: str) -> str:
    """Map a corpus filename to its context.md source_document slug.

    ``trackflow-returns-policy.en.md`` -> ``returns-policy``.
    """
    stem = filename
    for suffix in (".en.md", ".md"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    if stem.startswith("trackflow-"):
        stem = stem[len("trackflow-") :]
    # Drop a trailing language tag if the filename used a dotted form (returns-policy.en).
    stem = stem.split(".")[0]
    return stem


def _split_blocks(body: str) -> list[_Block]:
    """Split a document body into blank-line-separated paragraph blocks."""
    blocks: list[_Block] = []
    for raw in re.split(r"\n\s*\n", body.strip()):
        para = raw.strip("\n")
        if not para.strip():
            continue
        first_line = para.lstrip().splitlines()[0]
        blocks.append(_Block(text=para, is_list=bool(_LIST_ITEM.match(first_line))))
    return blocks


def _group_blocks(blocks: list[_Block]) -> list[str]:
    """Glue lists to their intro paragraph and colon-intros to the following block."""
    chunks: list[str] = []
    i = 0
    while i < len(blocks):
        buffer = [blocks[i].text]
        # Glue any lists that immediately follow this paragraph.
        while i + 1 < len(blocks) and blocks[i + 1].is_list:
            i += 1
            buffer.append(blocks[i].text)
        # A short colon-terminated lead-in belongs with the block it introduces.
        if buffer[-1].rstrip().endswith(":") and i + 1 < len(blocks) and not blocks[i + 1].is_list:
            i += 1
            buffer.append(blocks[i].text)
            while i + 1 < len(blocks) and blocks[i + 1].is_list:
                i += 1
                buffer.append(blocks[i].text)
        chunks.append("\n\n".join(buffer).strip())
        i += 1
    return chunks


def _derive_section(title: str, chunk_text: str) -> str:
    """Use the document title, refined with a short leading ``Label:`` when present."""
    first_line = chunk_text.lstrip().splitlines()[0] if chunk_text.strip() else ""
    match = _LABEL_LEAD.match(first_line)
    if match:
        return f"{title} — {match.group(1).strip()}"
    return title


def _extract_title(markdown: str) -> tuple[str, str]:
    """Return (title, body) splitting off a leading ``# H1`` heading if present."""
    lines = markdown.strip().splitlines()
    if lines and lines[0].lstrip().startswith("# "):
        title = lines[0].lstrip()[2:].strip()
        body = "\n".join(lines[1:])
        return title, body
    return "", markdown


def chunk_document(markdown: str, source_document: str) -> list[Chunk]:
    """Split one knowledge-base document into ordered, self-contained chunks.

    Raises ``ValueError`` if the document yields no chunks so an empty or malformed source
    fails loudly at index time rather than silently indexing nothing.
    """
    title, body = _extract_title(markdown)
    title = title or source_document
    texts = [text for text in _group_blocks(_split_blocks(body)) if text.strip()]
    if not texts:
        raise ValueError(f"Document '{source_document}' produced no chunks")
    return [
        Chunk(
            source_document=source_document,
            section=_derive_section(title, text),
            chunk_index=index,
            text=text,
        )
        for index, text in enumerate(texts)
    ]
