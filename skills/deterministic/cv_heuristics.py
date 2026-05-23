"""
Deterministic CV text heuristics (regex / keywords only; no LLM).

Pure functions for MVP ``cv_parse_and_score`` skill and tests.
"""

from __future__ import annotations

import re
from typing import Any, Dict, Final, List, Sequence, Tuple

_MAX_CV_TEXT: Final[int] = 50_000

_DEFAULT_KEYWORDS: Final[Tuple[str, ...]] = (
    "python",
    "django",
    "sql",
    "postgresql",
    "api",
    "rest",
    "javascript",
    "typescript",
    "java",
    "aws",
    "docker",
    "kubernetes",
    "testing",
    "git",
)

_YEARS_RE: Final[re.Pattern[str]] = re.compile(
    r"(?P<n>\d{1,2})\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience",
    re.IGNORECASE,
)
_EMAIL_RE: Final[re.Pattern[str]] = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
)


def bound_cv_text(text: str, *, max_len: int = _MAX_CV_TEXT) -> str:
    s = text.strip()
    if not s:
        raise ValueError("cv_text must be non-empty")
    if len(s) > max_len:
        return s[:max_len]
    return s


def extract_signals(cv_text: str) -> Dict[str, Any]:
    """
    Extract a small structured signal dict from raw CV text.

    Returns keys: ``years_experience`` (int|None), ``matched_keywords`` (list),
    ``keyword_coverage`` (float in [0,1]), ``email_present`` (bool).
    """
    text = bound_cv_text(cv_text)
    lowered = text.lower()

    years: int | None = None
    for match in _YEARS_RE.finditer(text):
        years = int(match.group("n"))
        break
    if years is None:
        alt = re.search(r"(\d{1,2})\+?\s*years?", lowered)
        if alt:
            years = int(alt.group(1))

    matched: List[str] = []
    for kw in _DEFAULT_KEYWORDS:
        if kw in lowered:
            matched.append(kw)

    coverage = len(matched) / len(_DEFAULT_KEYWORDS) if _DEFAULT_KEYWORDS else 0.0
    email_present = _EMAIL_RE.search(text) is not None

    return {
        "years_experience": years,
        "matched_keywords": matched,
        "keyword_coverage": round(min(1.0, max(0.0, coverage)), 6),
        "email_present": email_present,
    }


def score_signals(signals: Dict[str, Any]) -> Tuple[float, float]:
    """
    Compute ``(normalized_score, confidence)`` in [0, 1] from extracted signals.

    Transparent weights: years (cap 10y), keyword coverage, email presence.
    """
    years = signals.get("years_experience")
    years_score = 0.0
    if isinstance(years, (int, float)) and years > 0:
        years_score = min(1.0, float(years) / 10.0)

    coverage = signals.get("keyword_coverage")
    if not isinstance(coverage, (int, float)):
        coverage = 0.0
    kw_score = float(coverage)

    email_bonus = 0.1 if signals.get("email_present") else 0.0

    raw = 0.45 * years_score + 0.45 * kw_score + email_bonus
    score = round(min(1.0, max(0.0, raw)), 6)

    observed = 0
    if years is not None:
        observed += 1
    if signals.get("matched_keywords"):
        observed += 1
    if signals.get("email_present"):
        observed += 1
    confidence = round({0: 0.25, 1: 0.45, 2: 0.65, 3: 0.85}.get(observed, 0.85), 6)

    return score, confidence
