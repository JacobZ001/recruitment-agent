"""
Recruiter-facing projection from an orchestration snapshot (read-only composition).

Uses persisted ``OrchestrationState`` fields and :mod:`runtime.inspection.decision_explainer`
only; no planner or transition policy.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping

from runtime.inspection.decision_explainer import (
    build_decision_summary_text,
    build_ranking_decision_dict,
)
from schemas.state_schema import OrchestrationState, PipelinePhase


def _recruiter_status_kind(phase: str) -> str:
    if phase == PipelinePhase.HIRED.value:
        return "hired"
    if phase == PipelinePhase.INACTIVE.value:
        return "inactive"
    return "active"


def _status_block(phase: str) -> Dict[str, Any]:
    return {"kind": _recruiter_status_kind(phase)}


def _scores_from_extensions(ext: Mapping[str, Any]) -> Dict[str, Any]:
    scores: Dict[str, Any] = {}
    if "decision.light_score" in ext or "decision.light_confidence" in ext:
        light: Dict[str, Any] = {}
        if "decision.light_score" in ext:
            light["normalized"] = ext["decision.light_score"]
        if "decision.light_confidence" in ext:
            light["confidence"] = ext["decision.light_confidence"]
        if light:
            scores["light"] = light
    if "decision.deep_score" in ext or "decision.deep_confidence" in ext:
        deep: Dict[str, Any] = {}
        if "decision.deep_score" in ext:
            deep["normalized"] = ext["decision.deep_score"]
        if "decision.deep_confidence" in ext:
            deep["confidence"] = ext["decision.deep_confidence"]
        if deep:
            scores["deep"] = deep
    return scores


def _ranking_block(ext: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Read model for ranking: ``stage`` / ``branch`` from snapshot ``ranking.*`` keys;
    ``explanation`` from :func:`build_ranking_decision_dict` (same persisted keys, no new policy).
    """
    branch = ext.get("ranking.branch")
    stage = ext.get("ranking.stage")
    if branch is None or stage is None:
        return {}
    if not str(branch).strip() or not str(stage).strip():
        return {}
    blob = build_ranking_decision_dict(dict(ext))
    explanation = ""
    if blob is not None:
        explanation = str(blob["ranking_decision"]["explanation"])
    return {
        "stage": stage,
        "branch": branch,
        "explanation": explanation,
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
    Compose a recruiter-facing dict from ``snapshot.extensions``, pipeline phase,
    and :func:`~runtime.inspection.decision_explainer.build_ranking_decision_dict` /
    :func:`~runtime.inspection.decision_explainer.build_decision_summary_text`.

    ``pipeline.phase`` (exposed as ``stage``) is the single source of truth for UI state;
    no secondary status layer is maintained beyond aggregate ``status.kind``.
    """
    ext = dict(snapshot.extensions or {})
    # pipeline.phase is authoritative for where the candidate is in the workflow graph.
    stage = snapshot.pipeline.phase.value
    status = _status_block(stage)

    summary_bits: List[str] = []
    decision_txt = build_decision_summary_text(ext)
    if decision_txt:
        summary_bits.append(decision_txt)

    rd = build_ranking_decision_dict(ext)
    if rd is not None:
        summary_bits.append(str(rd["ranking_decision"]["explanation"]))

    ir = ext.get("inactive.reason")
    if ir is not None and str(ir).strip():
        summary_bits.append(f"Inactive context: {ir!s}.")

    summary = " ".join(summary_bits).strip()
    if not summary:
        summary = f"Current pipeline stage is {stage!r}."

    ranking = _ranking_block(ext)
    return {
        "stage": stage,
        "status": status,
        "summary": summary,
        "scores": _scores_from_extensions(ext),
        "ranking": ranking,
        "next_actions": _next_actions_for_phase(stage),
    }
