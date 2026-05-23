"""
Deterministic ranking branch resolution for the reference vertical slice.

Policy only: no multi-candidate ranking math. ``TOP_K`` / ``NEXT_M`` are reserved for
future collection-based policy; today ``payload["ranking.branch"]`` overrides tests.

Defaults (documented):
- ``stage="light"``: ``mid_m`` preserves the historical questionnaire-first happy path.
- ``stage="deep"``: ``top_k`` matches automated shortlist-after-deep evaluation.
"""

from __future__ import annotations

from typing import Any, Dict, Literal

TOP_K = 10
NEXT_M = 10

RankingBranch = Literal["top_k", "mid_m", "reject"]


def resolve_ranking_branch(*, payload: Dict[str, Any], stage: Literal["light", "deep"]) -> RankingBranch:
    raw = (payload or {}).get("ranking.branch")
    if raw in ("top_k", "mid_m", "reject"):
        return raw  # type: ignore[return-value]
    if stage == "light":
        return "mid_m"
    return "top_k"
