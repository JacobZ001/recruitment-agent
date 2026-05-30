"""Shared dedup index helpers for candidate stores (R-013.1)."""

from __future__ import annotations

from typing import List, Optional, Sequence, Set, Tuple
from uuid import UUID

from schemas.candidate_schema import Candidate


def dedup_index_triple(candidate: Candidate) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    sig = candidate.dedup_signals
    return sig.normalized_email, sig.normalized_phone, sig.cv_content_fingerprint


def filter_excluded(
    ids: Sequence[UUID],
    *,
    exclude_candidate_ids: Optional[Sequence[UUID]] = None,
) -> List[UUID]:
    excluded: Set[UUID] = set(exclude_candidate_ids or ())
    return [uid for uid in ids if uid not in excluded]
