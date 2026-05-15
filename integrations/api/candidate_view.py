"""
Recruiter-facing projection from an orchestration snapshot (read-only composition).

Maps only persisted ``OrchestrationState.pipeline`` and ``snapshot.extensions`` keys
into a stable JSON shape; no planner, transition engine, or inspection explainer calls.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Tuple

from schemas.state_schema import OrchestrationState, PipelinePhase

# Fixed copy for read model until model-based narrative is persisted (see tech_debt).
CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER = (
    "Not available (model-based evaluation under development)"
)

_RANKING_NOTE = "ranking not available in single-candidate mode"

# Minimal layout: (name, source) only. Per-criterion scores are not persisted yet.
# future: populated by cognition layer (dynamic per role / recruiter)
_CRITERIA_LAYOUT: Tuple[Tuple[str, str], ...] = (
    ("communication", "universal"),
    ("technical", "role_specific"),
    ("professionalism", "recruiter_preference"),
)


def _recruiter_status_kind(phase: str) -> str:
    if phase == PipelinePhase.HIRED.value:
        return "hired"
    if phase == PipelinePhase.INACTIVE.value:
        return "inactive"
    return "active"


def _status_block(phase: str) -> Dict[str, Any]:
    return {"kind": _recruiter_status_kind(phase)}


def _float_or_null(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _criteria_from_layout() -> List[Dict[str, Any]]:
    """Placeholder criteria rows until per-dimension scores exist in snapshot extensions."""
    return [
        {
            "name": name,
            "score": None,
            "confidence": None,
            "source": source,
        }
        for name, source in _CRITERIA_LAYOUT
    ]


def _overall_score_from_extensions(ext: Mapping[str, Any]) -> Dict[str, Any]:
    deep_s = _float_or_null(ext.get("decision.deep_score"))
    if deep_s is not None:
        return {"value": deep_s, "type": "deep"}
    light_s = _float_or_null(ext.get("decision.light_score"))
    if light_s is not None:
        return {"value": light_s, "type": "light"}
    return {"value": None, "type": None}


def _scores_section(ext: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "criteria": _criteria_from_layout(),
        "overall_score": _overall_score_from_extensions(ext),
    }


def _ranking_section(_ext: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Global rank placeholder only.

    ``ranking.stage`` on the snapshot records which *scoring* pass last applied ranking
    policy (light vs deep), not a recruiter-facing rank; use ``scores.overall_score.type``
    for that. Do not expose ``ranking.stage`` or ``ranking.branch`` here.
    """
    return {
        "rank": None,
        "total_candidates": None,
        "note": _RANKING_NOTE,
    }


def _next_actions_for_phase(phase: str) -> List[str]:
    """Static recruiter hints aligned with the demo slice (copy only; not transition policy)."""
    # TODO: derive from transition engine (tech debt); static hints only for demo slice.
    if phase == PipelinePhase.INACTIVE.value:
        return [
            "Review inactive reason in snapshot extensions; a recruiter may publish "
            "recruiter_reconsider_candidate when policy allows recovery."
        ]
    if phase == PipelinePhase.HIRED.value:
        return []
    hints: Dict[str, List[str]] = {
        PipelinePhase.SHORTLISTED.value: [
            "Schedule interview: recruiter_schedule_interview",
            "After the interview: recruiter_complete_interview",
            "Then: recruiter_send_offer, and candidate_accept_offer or candidate_decline_offer",
        ],
        PipelinePhase.INTERVIEW_PENDING.value: [
            "When the interview is done: recruiter_complete_interview",
        ],
        PipelinePhase.INTERVIEW_COMPLETED.value: [
            "Send an offer: recruiter_send_offer",
        ],
        PipelinePhase.OFFER_SENT.value: [
            "Record outcome: candidate_accept_offer or candidate_decline_offer",
        ],
        PipelinePhase.DEEP_SCORED.value: [
            "Shortlist from deep scoring: recruiter_shortlist_candidate (when in the correct phase)",
        ],
    }
    return list(hints.get(phase, ()))


def build_candidate_view(snapshot: OrchestrationState) -> Dict[str, Any]:
    """
    Compose a recruiter-facing dict from ``snapshot.extensions`` and pipeline phase.

    ``pipeline.phase`` (exposed as ``stage``) is the single source of truth for UI state;
    no secondary status layer is maintained beyond aggregate ``status.kind``.
    """
    ext = dict(snapshot.extensions or {})
    # pipeline.phase is authoritative for where the candidate is in the workflow graph.
    stage = snapshot.pipeline.phase.value
    status = _status_block(stage)

    return {
        "stage": stage,
        "status": status,
        "summary": CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER,
        "scores": _scores_section(ext),
        "ranking": _ranking_section(ext),
        "next_actions": _next_actions_for_phase(stage),
    }
