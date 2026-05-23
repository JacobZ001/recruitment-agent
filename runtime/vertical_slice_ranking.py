"""
Backward-compatible shim; canonical module is ``modules.recruitment.ranking``.

Compatibility shim — removal planned after multi-candidate stabilization. Import from
``modules.recruitment.ranking`` in new code.
"""

from modules.recruitment.ranking import (
    NEXT_M,
    TOP_K,
    RankingBranch,
    resolve_ranking_branch,
)

__all__ = ("NEXT_M", "TOP_K", "RankingBranch", "resolve_ranking_branch")
