"""Deterministic RFP section evaluators (readability, relevance, §5 compliance)."""

from __future__ import annotations

from central_api.domains.rfp.evaluators import (
    evaluate_compliance,
    evaluate_readability,
    evaluate_relevance,
    evaluate_section,
)

# A fully compliant USD warehouse draft used as the base for single-rule mutations.
COMPLIANT = (
    "Our warehouse offers storage capacity for your monthly orders, priced in USD. We commit to a "
    "98% on-time delivery SLA. Returns are completed in 72 hours. A volume-based discount tier table "
    "gives lower prices at higher volumes."
)


def test_readability_rejects_too_short() -> None:
    passed, detail = evaluate_readability("Too short to size.")
    assert passed is False
    assert detail["word_count"] < 20


def test_readability_accepts_reasonable_prose() -> None:
    passed, _ = evaluate_readability(COMPLIANT)
    assert passed is True


def test_relevance_matches_department_or_aspects() -> None:
    passed, detail = evaluate_relevance(COMPLIANT, "warehouse", ["storage capacity"])
    assert passed is True
    assert "warehouse" in detail["matched_terms"] or "storage" in detail["matched_terms"]


def test_relevance_rejects_off_topic_thin_text() -> None:
    passed, _ = evaluate_relevance("Nothing relevant here at all.", "warehouse", ["storage"])
    assert passed is False


def test_compliance_passes_for_compliant_draft() -> None:
    passed, issues = evaluate_compliance(COMPLIANT, "USD")
    assert passed is True and issues == []


def test_compliance_flags_wrong_currency() -> None:
    passed, issues = evaluate_compliance(COMPLIANT + " Also billed in €500 tranches.", "USD")
    assert passed is False and "wrong_currency" in issues


def test_compliance_flags_missing_sla() -> None:
    text = "Warehouse storage in USD. Returns take 72 hours. A volume-based discount tier table applies."
    passed, issues = evaluate_compliance(text, "USD")
    assert passed is False and "missing_sla" in issues


def test_compliance_flags_returns_under_48h() -> None:
    text = COMPLIANT.replace("72 hours", "24 hours")
    passed, issues = evaluate_compliance(text, "USD")
    assert passed is False and "returns_under_48h" in issues


def test_compliance_flags_missing_discount_tiers() -> None:
    text = "Warehouse storage in USD with a 98% on-time delivery SLA. Returns complete in 72 hours."
    passed, issues = evaluate_compliance(text, "USD")
    assert passed is False and "missing_discount_tiers" in issues


def test_compliance_flags_disclosed_carrier_rates() -> None:
    text = COMPLIANT + " We pass through a negotiated carrier rate from our partners."
    passed, issues = evaluate_compliance(text, "USD")
    assert passed is False and "discloses_carrier_rates" in issues


def test_evaluate_section_consolidates_pass() -> None:
    result = evaluate_section(COMPLIANT, currency="USD", department_id="warehouse", key_aspects=["storage"])
    assert result.passed is True
    assert result.results["compliance"]["passed"] is True
    assert result.issues == []


def test_evaluate_section_consolidates_failure_feedback() -> None:
    text = COMPLIANT.replace("72 hours", "24 hours").replace("98% on-time delivery SLA", "great service")
    result = evaluate_section(text, currency="USD", department_id="warehouse", key_aspects=["storage"])
    assert result.passed is False
    assert "returns_under_48h" in result.issues and "missing_sla" in result.issues
