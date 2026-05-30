"""Deterministic materialized scoring-context fingerprint (R-014)."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Mapping, Optional, Sequence

from schemas.state_schema import ScoringContext


def _normalize_string_list(values: Sequence[str]) -> List[str]:
    return sorted({str(item).strip() for item in values if str(item).strip()})


def _typed_block_without_source_refs(context: Any) -> Optional[Dict[str, Any]]:
    if context is None:
        return None
    if hasattr(context, "model_dump"):
        payload = context.model_dump(mode="json")
    else:
        payload = dict(context)
    payload.pop("source_refs", None)
    for key, value in list(payload.items()):
        if isinstance(value, list):
            payload[key] = _normalize_string_list(value)
    return payload


def materialized_scoring_context_fingerprint(context: ScoringContext) -> str:
    """
    Hash of the five materialized blocks only (org, recruiter, job, L2, L3).

    Excludes prose, metadata, source_refs, and version fields.
    """
    blocks = [
        _typed_block_without_source_refs(context.organization_context),
        _typed_block_without_source_refs(context.recruiter_actor_context),
        _typed_block_without_source_refs(context.job_context),
        _normalize_string_list(context.derived_l2_criteria),
        _normalize_string_list(context.derived_l3_criteria),
    ]
    canonical = json.dumps(blocks, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
