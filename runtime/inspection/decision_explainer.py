"""
Structured explanations for inspection UIs (read-only; no orchestration).

Ranking is implicit in the planner; this module maps persisted transition extensions
to human-readable ``ranking_decision`` payloads for timelines and tooling.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from schemas.state_schema import OrchestrationState, StateTransitionRecord

_MAX_EVIDENCE_REFS = 6

_EXPLANATIONS: Dict[tuple[str, str], str] = {
    ("light", "top_k"): "Shortlisted immediately after light scoring (top bucket).",
    ("light", "mid_m"): "Candidate placed in questionnaire bucket (mid tier).",
    ("light", "reject"): "Excluded after light scoring (ranking reject).",
    ("deep", "top_k"): "Shortlisted after deep scoring (top bucket).",
    ("deep", "reject"): "Excluded after deep scoring (ranking reject).",
}


def build_ranking_decision_dict(extensions: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Build a stable ``ranking_decision`` object from transition ``extensions`` keys.

    Returns ``None`` when no ranking keys are present.
    """
    branch = extensions.get("ranking.branch")
    stage = extensions.get("ranking.stage")
    if branch is None or stage is None:
        return None
    key = (str(stage), str(branch))
    explanation = _EXPLANATIONS.get(
        key,
        "Deterministic ranking branch (see runtime.vertical_slice_ranking).",
    )
    return {
        "ranking_decision": {
            "stage": str(stage),
            "branch": str(branch),
            "explanation": explanation,
        }
    }


def evidence_refs_from_extensions(ex: Mapping[str, Any]) -> Optional[List[str]]:
    refs = ex.get("decision.evidence_refs")
    if isinstance(refs, list) and refs:
        return [str(x) for x in refs[:_MAX_EVIDENCE_REFS]]
    return None


def format_hard_filter_from_extensions(ex: Mapping[str, Any]) -> Optional[str]:
    """Single-line summary from persisted ``decision.hard_filter_pass`` (snapshot only)."""
    if "decision.hard_filter_pass" not in ex:
        return None
    return f"filter computed_pass={ex.get('decision.hard_filter_pass')!r} (from snapshot)"


def format_light_scoring_from_extensions(ex: Mapping[str, Any]) -> Optional[str]:
    """Single-line summary from persisted light score keys (snapshot only)."""
    if "decision.light_score" not in ex:
        return None
    return (
        f"kind=light normalized={ex.get('decision.light_score')!r} "
        f"confidence_numeric={ex.get('decision.light_confidence')!r} (from snapshot)"
    )


def format_deep_scoring_from_extensions(ex: Mapping[str, Any]) -> Optional[str]:
    """Single-line summary from persisted deep score keys (snapshot only)."""
    if "decision.deep_score" not in ex:
        return None
    return (
        f"kind=deep normalized={ex.get('decision.deep_score')!r} "
        f"confidence_numeric={ex.get('decision.deep_confidence')!r} (from snapshot)"
    )


def build_decision_summary_text(ex: Mapping[str, Any]) -> str:
    """
    Human-readable aggregate of persisted ``decision.*`` keys (read-only; no skill payloads).
    """
    bits: List[str] = []
    for fn in (
        format_hard_filter_from_extensions,
        format_light_scoring_from_extensions,
        format_deep_scoring_from_extensions,
    ):
        s = fn(ex)
        if s:
            bits.append(s)
    return " ".join(bits)


def ranking_timeline_lines_for_transition(tr: StateTransitionRecord) -> List[str]:
    """Indented timeline lines for one transition that carries ranking extensions."""
    ex = tr.extensions or {}
    if ex.get("ranking.branch") is None:
        return []
    return [
        f"    ranking.branch={ex.get('ranking.branch')}",
        f"    ranking.stage={ex.get('ranking.stage')}",
    ]


def ranking_timeline_lines_for_ingested_event(
    ns: OrchestrationState,
    ingested_event_id: Any,
) -> List[str]:
    """All ranking annotation lines for transitions committed under ``ingested_event_id``."""
    out: List[str] = []
    for tr in ns.transitions:
        if tr.event_id != ingested_event_id:
            continue
        out.extend(ranking_timeline_lines_for_transition(tr))
    return out
