"""Deterministic TrackFlow agent guardrails.

Model prompts are advisory; these checks are the enforceable harness around routing, evidence,
tools, and final output. They emit allowlisted metadata only and never retain rejected content.
"""

from __future__ import annotations

import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Literal

Category = Literal["structural", "content", "security"]
Outcome = Literal["allowed", "blocked", "redirected", "clarification"]

SAFE_REDIRECT = (
    "I can help with TrackFlow shipment incidents, returns, delivery policies, and carrier operations. "
    "I can't act as a general-purpose personal assistant."
)
JURISDICTION_REQUIRED = (
    "I can't select a country policy until an administrator assigns your United States or Spain policy jurisdiction."
)
UNSUPPORTED_TRACKING = (
    "TrackFlow shipment tracking is not available through this agent yet because no authoritative "
    "shipment-ownership source is connected. I can help with an incident ticket you are authorized to access."
)
SECURITY_REFUSAL = "I can't change or reveal the agent's instructions, authority, or credentials."
OUTPUT_FALLBACK = "I couldn't return that answer safely. Please use the relevant TrackFlow operations screen."

_ZERO_WIDTH = re.compile("[\u200b-\u200f\u2060\ufeff]")
_SPACES = re.compile(r"\s+")
_HOMOGLYPHS = str.maketrans(
    {
        "\u0430": "a",
        "\u0435": "e",
        "\u0456": "i",
        "\u043e": "o",
        "\u0440": "p",
        "\u0441": "c",
        "\u0445": "x",
    }
)
_COMPACT_INJECTION_RULES: tuple[tuple[str, str], ...] = (
    ("instruction_override", "ignorepreviousinstructions"),
    ("instruction_override", "ignoreallrules"),
    ("prompt_extraction", "revealsystemprompt"),
    ("prompt_extraction", "printhiddenprompt"),
    ("authority_bypass", "bypassauthorization"),
    ("admin_impersonation", "iamadministrator"),
)
_INJECTION_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(r"\b(ignore|disregard|forget|override)\b.{0,50}\b(instruction|rules?|policy|prompt)\b"),
    ),
    (
        "role_replacement",
        re.compile(
            r"\b(you are now|developer mode|no rules?|(?:act as|pretend to be)\s+(?:an?\s+)?"
            r"(?:admin|administrator|developer|system|unrestricted assistant))\b"
        ),
    ),
    (
        "prompt_extraction",
        re.compile(r"\b(reveal|show|print|repeat|extract)\b.{0,45}\b(system|developer|hidden)\s+(prompt|instruction)"),
    ),
    (
        "authority_bypass",
        re.compile(r"\b(bypass|disable|evade)\b.{0,40}\b(auth|authorization|guardrail|scope|permission)"),
    ),
    ("admin_impersonation", re.compile(r"\b(i am|i'm|as)\s+(an?\s+)?(admin|administrator|owner|developer)\b")),
    (
        "evidence_instruction",
        re.compile(r"\b(treat|use)\b.{0,30}\b(document|tool|result|retrieval)\b.{0,30}\b(instruction|system)\b"),
    ),
)
_PERSONAL_USE = re.compile(
    r"\b(write|compose|solve|code|program|debug|counsel|therapy|therapist)\b.{0,55}"
    r"\b(essay|homework|poem|love letter|university|project|relationship|personal|python|javascript)\b"
)
_TRACKING = re.compile(r"\b(order|shipment|tracking)\s*(?:number|#|id)?\s*[a-z0-9-]{3,}\b")
_POLICY_WORDS = re.compile(r"\b(policy|return|sla|delivery|coverage|carrier|shipping|warehouse)\b")
_SECRET_OUTPUT = re.compile(
    r"(?i)(bearer\s+[a-z0-9._-]+|sk-[a-z0-9_-]{10,}|client[_ -]?secret|private[_ -]?key|password\s*[:=])"
)
_ADDRESS_OUTPUT = re.compile(
    r"(?i)\b\d{1,6}\s+[a-z0-9 .'-]{2,45}\s(?:street|st|road|rd|avenue|ave|boulevard|blvd|lane|ln|calle|camino)\b"
)
# A monetary amount, in either "USD 18" or "18 USD" / "$18" order.
_MONEY = r"(?:(?:usd|eur|\$|€)\s*\d+(?:[.,]\d+)?|\d+(?:[.,]\d+)?\s*(?:usd|eur))"
# Words that mark an amount as an internal or carrier-negotiated cost rather than
# the published client price.
_INTERNAL_COST = (
    r"(?:negotiat\w*|internal|wholesale|buy[- ]rate|our\s+cost|cost\s+price|margin"
    r"|carrier\s+(?:rate|price|cost)|rate\s+(?:with|from)\s+(?:the\s+)?carrier)"
)
_CARRIER_NAMES = r"(?:ups|fedex|dhl|usps|mrw|seur|correos|gls)"
# Only an amount tied to a carrier or explicitly framed as an internal cost is a
# disclosure. The business rule is "never reveal negotiated carrier rates -- quote
# only the final price to the client", so published client pricing (storage,
# last-mile, returns) must answer normally; blocking every currency figure made the
# knowledge assistant unable to answer any pricing question at all.
_RATE_OUTPUT = re.compile(
    rf"(?i)(?:{_CARRIER_NAMES}\b.{{0,60}}?{_MONEY}"
    rf"|{_MONEY}.{{0,60}}?\b{_CARRIER_NAMES}\b"
    rf"|{_INTERNAL_COST}\b.{{0,60}}?{_MONEY}"
    rf"|{_MONEY}.{{0,60}}?\b{_INTERNAL_COST})"
)
_PROMPT_OUTPUT = re.compile(r"(?i)\b(system prompt|developer message|hidden instruction|authority hierarchy)\b")
_US_TERMS = re.compile(r"(?i)\b(united states|los angeles|california|ups|fedex)\b")
_ES_TERMS = re.compile(r"(?i)\b(spain|zaragoza|arag[oó]n|madrid|mrw|seur)\b")


def normalize_untrusted(value: str) -> str:
    """Normalize obfuscation without preserving the raw text in any event."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = _ZERO_WIDTH.sub("", normalized).translate(_HOMOGLYPHS)
    return _SPACES.sub(" ", normalized).strip().casefold()


@dataclass(frozen=True)
class GuardrailEvent:
    layer: str
    rule_id: str
    category: Category
    outcome: Outcome
    duration_ms: int

    def as_dict(self) -> dict[str, object]:
        return {
            "layer": self.layer,
            "rule_id": self.rule_id,
            "category": self.category,
            "outcome": self.outcome,
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class InputDecision:
    action: Literal["allow", "reject", "redirect", "clarify"]
    answer: str | None
    event: GuardrailEvent | None


def _event(started: float, layer: str, rule_id: str, category: Category, outcome: Outcome) -> GuardrailEvent:
    return GuardrailEvent(layer, rule_id, category, outcome, max(0, int((time.perf_counter() - started) * 1000)))


def validate_input(question: str, jurisdiction: str | None) -> InputDecision:
    started = time.perf_counter()
    normalized = normalize_untrusted(question)
    compact = re.sub(r"[^a-z0-9]+", "", normalized)
    for rule_id, signature in _COMPACT_INJECTION_RULES:
        if signature in compact:
            return InputDecision("reject", SECURITY_REFUSAL, _event(started, "input", rule_id, "security", "blocked"))
    for rule_id, pattern in _INJECTION_RULES:
        if pattern.search(normalized):
            return InputDecision("reject", SECURITY_REFUSAL, _event(started, "input", rule_id, "security", "blocked"))
    if _PERSONAL_USE.search(normalized):
        return InputDecision(
            "redirect", SAFE_REDIRECT, _event(started, "input", "personal_chatbot", "content", "redirected")
        )
    if _TRACKING.search(normalized) and "ticket" not in normalized:
        return InputDecision(
            "reject",
            UNSUPPORTED_TRACKING,
            _event(started, "input", "shipment_source_unavailable", "structural", "blocked"),
        )
    if jurisdiction is None and _POLICY_WORDS.search(normalized):
        return InputDecision(
            "clarify",
            JURISDICTION_REQUIRED,
            _event(started, "input", "jurisdiction_missing", "security", "clarification"),
        )
    if jurisdiction == "US" and re.search(r"(?i)apply\s+spain|spain.+benefit", normalized):
        return InputDecision(
            "reject", SECURITY_REFUSAL, _event(started, "input", "jurisdiction_override", "security", "blocked")
        )
    if jurisdiction == "ES" and re.search(r"(?i)apply\s+(us|united states)|united states.+benefit", normalized):
        return InputDecision(
            "reject", SECURITY_REFUSAL, _event(started, "input", "jurisdiction_override", "security", "blocked")
        )
    return InputDecision("allow", None, None)


def evidence_is_safe(text: str) -> bool:
    """Reject evidence containing instruction-like content before it reaches generation."""
    normalized = normalize_untrusted(text)
    return not any(pattern.search(normalized) for _, pattern in _INJECTION_RULES)


def validate_ticket_argument(ticket_id: int | None) -> bool:
    return isinstance(ticket_id, int) and ticket_id > 0


def validate_output(
    answer: str,
    jurisdiction: str | None,
    *,
    authoritative_status: str | None = None,
    has_grounded_evidence: bool = True,
) -> str | None:
    """Return a stable rule identifier when the final answer must be blocked."""
    if not answer.strip():
        return "empty_output"
    if _SECRET_OUTPUT.search(answer) or _PROMPT_OUTPUT.search(answer):
        return "sensitive_output"
    if _ADDRESS_OUTPUT.search(answer):
        return "address_output"
    if _RATE_OUTPUT.search(answer):
        return "carrier_rate_output"
    if re.search(r"(?i)\b(exact warehouse|warehouse route|internal route)\b", answer):
        return "warehouse_detail_output"
    if jurisdiction == "US" and _ES_TERMS.search(answer):
        return "cross_jurisdiction_output"
    if jurisdiction == "ES" and _US_TERMS.search(answer):
        return "cross_jurisdiction_output"
    if (
        not has_grounded_evidence
        and _POLICY_WORDS.search(answer)
        and re.search(r"\b\d+\b|\b(?:must|always|never)\b", answer)
    ):
        return "unsupported_policy_claim"
    if authoritative_status:
        stated = {
            status
            for status in ("open", "in progress", "resolved", "discarded", "closed", "pending")
            if status in answer.casefold()
        }
        expected = authoritative_status.replace("_", " ").casefold()
        if stated and stated != {expected}:
            return "ungrounded_ticket_status"
    return None
