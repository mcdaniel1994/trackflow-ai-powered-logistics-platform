"""Deterministic readability metrics (no provider, no nltk)."""

from __future__ import annotations

from central_api.domains.rfp.readability import compute_readability, readability_dict


def test_counts_simple_sentence() -> None:
    metrics = compute_readability("The cat sat on the mat.")
    assert metrics.word_count == 6
    assert metrics.sentence_count == 1
    assert metrics.syllable_count >= 6


def test_empty_text_is_zeroed() -> None:
    metrics = compute_readability("   ")
    assert metrics.word_count == 0
    assert metrics.flesch_kincaid_grade == 0.0
    assert metrics.gunning_fog == 0.0


def test_complex_text_scores_higher_grade() -> None:
    simple = compute_readability("The dog ran. The cat sat. We go home.")
    dense = compute_readability(
        "Sophisticated logistics optimization necessitates comprehensive infrastructure evaluation."
    )
    assert dense.flesch_kincaid_grade > simple.flesch_kincaid_grade


def test_is_deterministic() -> None:
    text = "Ship the order today. Track the delivery tomorrow."
    assert compute_readability(text) == compute_readability(text)


def test_readability_dict_is_json_safe() -> None:
    data = readability_dict("Ship the order today.")
    assert set(data) == {
        "word_count",
        "sentence_count",
        "syllable_count",
        "flesch_kincaid_grade",
        "gunning_fog",
    }
    assert all(isinstance(value, (int, float)) for value in data.values())
