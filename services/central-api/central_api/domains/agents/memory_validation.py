"""Deterministic never-store policy for confirmed structured memory."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from ..suppliers.models import Supplier
from .schemas import MemoryCandidate

ACTIVE_CARRIER_NAMES = frozenset(
    {
        "UPS Ground",
        "FedEx Ground",
        "DHL Express USA",
        "OnTrac",
        "MRW España",
        "SEUR",
        "DHL Express España",
        "Nacex",
    }
)

_ADDRESS = re.compile(
    r"(?i)\b\d{1,6}\s+[a-záéíóúñ0-9 .'-]{2,50}\s"
    r"(?:street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln|calle|camino|plaza|paseo)\b"
)
_PERSONAL = re.compile(
    r"(?i)(\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b|\b(?:\+?\d[\d .()-]{8,}\d)\b|"
    r"\b(?:ssn|dni|passport|customer name|recipient name|personal data|date of birth)\b)"
)
_WAREHOUSE = re.compile(r"(?i)\b(warehouse|dock|aisle|bin|shelf|loading bay|route through|internal route)\b")
_ISOLATED = re.compile(r"(?i)\b(ticket|incident|order|shipment)\s*(?:#|id|number)?\s*[a-z0-9-]{2,}\b")
_NEGOTIATION = re.compile(r"(?i)\b(negotiat|contract rate|carrier rate|quote|bid|discount|pricing|price)\w*\b")
_SECRET = re.compile(
    r"(?i)\b(password|secret|credential|api[_ -]?key|access[_ -]?token|refresh[_ -]?token|bearer)\b|"
    r"sk-[a-z0-9_-]{8,}"
)
_PROMPT = re.compile(r"(?i)\b(system prompt|developer message|hidden instruction|prompt fragment)\b")
_TOOL_ARGUMENT = re.compile(r"(?i)\b(tool argument|function call|ticket_id|sku_id|subject_token)\b|\{\s*\"")
_RAW_RETRIEVAL = re.compile(r"(?i)\b(raw retrieved|retrieved chunk|source_document|qdrant payload|rag payload)\b")
_EXECUTABLE = re.compile(
    r"(?i)(```|<script|\b(?:import|def|class|function|eval|exec)\s+[a-z_(]|\b(?:select|insert|update|delete)\s+.+\bfrom\b)"
)
_INSTRUCTION_CHANGE = re.compile(
    r"(?i)\b(ignore|override|change|disable|bypass)\b.{0,45}\b(instruction|rule|policy|guardrail|authorization)\b"
)
_US_ONLY = re.compile(r"(?i)\b(ups|fedex|ontrac|united states|usa|los angeles|california)\b")
_ES_ONLY = re.compile(r"(?i)\b(mrw|seur|nacex|spain|españa|zaragoza|arag[oó]n)\b")


@dataclass(frozen=True)
class MemoryValidationError(ValueError):
    reason_code: str


def _normalized(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


def validate_memory_candidate(
    candidate: MemoryCandidate,
    *,
    supplier: Supplier | None,
    authenticated_jurisdiction: str,
) -> None:
    """Raise a stable reason before any proposal row can be written."""
    fact = _normalized(candidate.fact)
    if candidate.recurrence_count < 2:
        raise MemoryValidationError("recurrence_below_two")
    if candidate.jurisdiction != authenticated_jurisdiction:
        raise MemoryValidationError("jurisdiction_mismatch")
    if supplier is None or supplier.name not in ACTIVE_CARRIER_NAMES:
        raise MemoryValidationError("carrier_not_authoritative")
    if supplier.status != "active" or not any(category.startswith("carrier_") for category in supplier.categories):
        raise MemoryValidationError("carrier_inactive")
    expected_country = "USA" if candidate.jurisdiction == "US" else "Spain"
    if supplier.country != expected_country:
        raise MemoryValidationError("carrier_country_mismatch")

    checks = (
        (_ADDRESS, "address"),
        (_PERSONAL, "personal_data"),
        (_WAREHOUSE, "warehouse_detail"),
        (_ISOLATED, "isolated_incident"),
        (_NEGOTIATION, "negotiation"),
        (_SECRET, "credential_or_secret"),
        (_PROMPT, "prompt_content"),
        (_TOOL_ARGUMENT, "tool_argument"),
        (_RAW_RETRIEVAL, "raw_retrieval"),
        (_EXECUTABLE, "executable_content"),
        (_INSTRUCTION_CHANGE, "instruction_change"),
    )
    for pattern, reason in checks:
        if pattern.search(fact):
            raise MemoryValidationError(reason)
    if candidate.jurisdiction == "US" and _ES_ONLY.search(fact):
        raise MemoryValidationError("cross_country_fact")
    if candidate.jurisdiction == "ES" and _US_ONLY.search(fact):
        raise MemoryValidationError("cross_country_fact")
