"""Deterministic CV heuristics."""

from __future__ import annotations

import pytest

from skills.deterministic.cv_heuristics import extract_signals, score_signals


_SAMPLE_CV = """
Jane Doe
jane.doe@example.com
Senior Python Engineer

8 years of experience building REST APIs with Django and PostgreSQL.
Skills: Python, Django, SQL, testing, git.
"""


def test_extract_signals_finds_years_keywords_email() -> None:
    signals = extract_signals(_SAMPLE_CV)
    assert signals["years_experience"] == 8
    assert signals["email_present"] is True
    assert "python" in signals["matched_keywords"]
    assert "django" in signals["matched_keywords"]
    assert 0.0 < signals["keyword_coverage"] <= 1.0


def test_score_signals_is_deterministic() -> None:
    signals = extract_signals(_SAMPLE_CV)
    a = score_signals(signals)
    b = score_signals(signals)
    assert a == b
    score, confidence = a
    assert 0.0 <= score <= 1.0
    assert 0.0 <= confidence <= 1.0


def test_extract_signals_empty_raises() -> None:
    with pytest.raises(ValueError):
        extract_signals("   ")
