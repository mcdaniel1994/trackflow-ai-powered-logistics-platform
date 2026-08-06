"""Deterministic, dependency-free readability metrics for intake sizing.

Used to anticipate how expensive an RFP will be to process, not to judge writing quality. Computed
in pure Python (no ``nltk`` / ``py-readability-metrics``, which need a runtime corpus download that
fails in offline CI). Fully deterministic, so results are testable without mocks.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

_WORD_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
_SENTENCE_RE = re.compile(r"[.!?]+")
_VOWEL_GROUP_RE = re.compile(r"[aeiouyáéíóúü]+", re.IGNORECASE)


@dataclass(frozen=True)
class ReadabilityMetrics:
    word_count: int
    sentence_count: int
    syllable_count: int
    flesch_kincaid_grade: float
    gunning_fog: float


def _count_syllables(word: str) -> int:
    """Approximate syllables by counting vowel groups; every word has at least one."""
    return max(1, len(_VOWEL_GROUP_RE.findall(word)))


def compute_readability(text: str) -> ReadabilityMetrics:
    """Compute Flesch-Kincaid grade and Gunning Fog for the converted document text."""
    words = _WORD_RE.findall(text)
    word_count = len(words)
    # A trailing sentence without terminal punctuation still counts as one.
    sentence_count = max(1, len([s for s in _SENTENCE_RE.split(text) if s.strip()]))
    if word_count == 0:
        return ReadabilityMetrics(0, sentence_count, 0, 0.0, 0.0)

    syllables = [_count_syllables(word) for word in words]
    syllable_count = sum(syllables)
    complex_words = sum(1 for count in syllables if count >= 3)

    words_per_sentence = word_count / sentence_count
    syllables_per_word = syllable_count / word_count
    fk_grade = 0.39 * words_per_sentence + 11.8 * syllables_per_word - 15.59
    fog = 0.4 * (words_per_sentence + 100 * (complex_words / word_count))
    return ReadabilityMetrics(
        word_count=word_count,
        sentence_count=sentence_count,
        syllable_count=syllable_count,
        flesch_kincaid_grade=round(fk_grade, 2),
        gunning_fog=round(fog, 2),
    )


def readability_dict(text: str) -> dict[str, float | int]:
    """Metrics as a JSON-safe dict for persistence in ``rfp_tickets.readability_metrics``."""
    return asdict(compute_readability(text))
