"""Deterministic evaluators for generated RFP proposal sections.

Three checks run over each draft: readability, relevance, and compliance with TrackFlow's business
guidelines (agentic_workflows_context.md §5). Every check is deterministic and rule-based — not an
LLM judgment — so results are verifiable and testable without a provider. A failing check returns
concrete, non-sensitive feedback the generator can act on.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .readability import compute_readability

READABILITY_MAX_GRADE = 16.0  # denser than a college senior reads poorly for a business proposal
MIN_WORDS = 20

_HOURS_RE = re.compile(r"(\d{1,3})\s*-?\s*hour", re.IGNORECASE)
_SAME_NEXT_DAY_RE = re.compile(r"\b(same[- ]day|next[- ]day|24[- ]?h)\b", re.IGNORECASE)
_NEGOTIATED_RATE_RE = re.compile(r"negotiat\w*\s+(carrier\s+)?rate", re.IGNORECASE)


@dataclass
class EvaluationResult:
    passed: bool
    results: dict[str, Any]
    issues: list[str] = field(default_factory=list)


def evaluate_readability(text: str) -> tuple[bool, dict[str, Any]]:
    metrics = compute_readability(text)
    passed = metrics.word_count >= MIN_WORDS and metrics.flesch_kincaid_grade <= READABILITY_MAX_GRADE
    return passed, {"flesch_kincaid_grade": metrics.flesch_kincaid_grade, "word_count": metrics.word_count}


def evaluate_relevance(text: str, department_id: str, key_aspects: list[str]) -> tuple[bool, dict[str, Any]]:
    lowered = text.lower()
    tokens = [department_id] + [word for aspect in key_aspects for word in aspect.lower().split()]
    matched = [token for token in dict.fromkeys(tokens) if len(token) > 3 and token in lowered]
    passed = len(text.split()) >= MIN_WORDS and (department_id in lowered or len(matched) > 0)
    return passed, {"matched_terms": matched}


def _returns_under_48h(lowered: str) -> bool:
    if _SAME_NEXT_DAY_RE.search(lowered) and "return" in lowered:
        return True
    for match in _HOURS_RE.finditer(lowered):
        hours = int(match.group(1))
        window = lowered[max(0, match.start() - 60) : match.end() + 20]
        if hours < 48 and "return" in window:
            return True
    return False


def evaluate_compliance(text: str, currency: str | None) -> tuple[bool, list[str]]:
    lowered = text.lower()
    issues: list[str] = []

    if currency == "USD" and ("€" in text or "eur" in lowered):
        issues.append("wrong_currency")
    if currency == "EUR" and ("$" in text or "usd" in lowered):
        issues.append("wrong_currency")
    if currency == "USD" and not ("$" in text or "usd" in lowered):
        issues.append("missing_currency")
    if currency == "EUR" and not ("€" in text or "eur" in lowered):
        issues.append("missing_currency")

    has_sla = "%" in text and any(term in lowered for term in ("sla", "on-time", "on time", "delivery"))
    if not has_sla:
        issues.append("missing_sla")

    if _returns_under_48h(lowered):
        issues.append("returns_under_48h")

    if not ("discount" in lowered and ("tier" in lowered or "volume" in lowered)):
        issues.append("missing_discount_tiers")

    if _NEGOTIATED_RATE_RE.search(text):
        issues.append("discloses_carrier_rates")

    return len(issues) == 0, issues


def evaluate_section(
    text: str,
    *,
    currency: str | None,
    department_id: str,
    key_aspects: list[str],
) -> EvaluationResult:
    """Run all three evaluators and consolidate pass/fail plus actionable feedback."""
    readable, readability = evaluate_readability(text)
    relevant, relevance = evaluate_relevance(text, department_id, key_aspects)
    compliant, compliance_issues = evaluate_compliance(text, currency)

    issues: list[str] = []
    if not readable:
        issues.append("readability")
    if not relevant:
        issues.append("relevance")
    issues.extend(compliance_issues)

    return EvaluationResult(
        passed=readable and relevant and compliant,
        results={
            "readability": {"passed": readable, **readability},
            "relevance": {"passed": relevant, **relevance},
            "compliance": {"passed": compliant, "issues": compliance_issues},
        },
        issues=issues,
    )
