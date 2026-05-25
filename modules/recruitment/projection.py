"""
Read-only recruitment projections (snapshots, timelines, demo fixtures).

No planner, transition engine, or state mutation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple
from uuid import UUID

from orchestrator.vertical_slice_planner import (
    SKILL_DEEP_SCORING,
    SKILL_HARD_FILTER,
    SKILL_LIGHT_SCORING,
)
from .fixtures import DEMO_CANDIDATE_DISPLAY
from .inspection.timeline import vertical_slice_timeline_text
from runtime.inspection import skill_decision_summary_parts
from schemas.state_schema import (
    EvaluationState,
    OrchestrationState,
    PipelinePhase,
)

from .exceptions import CandidateNotFoundError
from .policies import get_available_actions_for_phase

CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER = (
    "Not available (model-based evaluation under development)"
)

_RANKING_NOTE = "ranking not available in single-candidate mode"

_CRITERIA_LAYOUT: Tuple[Tuple[str, str], ...] = (
    ("communication", "universal"),
    ("ownership", "universal"),
    ("reliability", "universal"),
    ("thinking", "universal"),
)


class ReadRuntime(Protocol):
    """Runtime surface for read-only projections."""

    @property
    def candidate_id(self) -> UUID: ...

    @property
    def bundle(self) -> Any: ...


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


def _model_dump_json(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _evaluation_from_snapshot(snapshot: OrchestrationState) -> Optional[EvaluationState]:
    return snapshot.evaluation


def _summary_from_snapshot(snapshot: OrchestrationState) -> str:
    profile = snapshot.ingress_profile
    if profile is not None and profile.summary.strip():
        return profile.summary
    return CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER


def _criteria_from_layout(evaluation: Optional[EvaluationState]) -> List[Dict[str, Any]]:
    light = evaluation.light if evaluation is not None else None
    return [
        {
            "name": name,
            "score": None if light is None or name not in light.criteria else float(light.criteria[name].score),
            "confidence": (
                None
                if light is None or name not in light.criteria
                else float(light.criteria[name].confidence)
            ),
            "source": source,
            "reason": None if light is None or name not in light.criteria else light.criteria[name].reason,
        }
        for name, source in _CRITERIA_LAYOUT
    ]


def _overall_score_from_evaluation(evaluation: Optional[EvaluationState]) -> Dict[str, Any]:
    if evaluation is not None and evaluation.deep is not None:
        return {"value": float(evaluation.deep.normalized_score), "type": "deep"}
    if evaluation is not None and evaluation.light is not None:
        return {"value": float(evaluation.light.normalized_score), "type": "light"}
    return {"value": None, "type": None}


def _scores_section(evaluation: Optional[EvaluationState]) -> Dict[str, Any]:
    return {
        "criteria": _criteria_from_layout(evaluation),
        "overall_score": _overall_score_from_evaluation(evaluation),
    }


def _ranking_section(_ext: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "rank": None,
        "total_candidates": None,
        "note": _RANKING_NOTE,
    }


def _next_actions_for_phase(phase: str) -> List[str]:
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


def _candidate_id_from_snapshot(snapshot: OrchestrationState) -> Optional[UUID]:
    for link in snapshot.links:
        if link.kind.strip().lower() == "candidate":
            return link.id
    return None


def build_candidate_list_item(snapshot: OrchestrationState) -> Dict[str, Any]:
    """
    Lightweight list row from ``snapshot`` (stage, status kind, overall score).

    ``overall_score`` uses the same deep-then-light rule as :func:`build_candidate_view`
    (via :func:`_overall_score_from_extensions`). Does not include criteria, timeline,
    ranking detail, or evaluation summary.
    """
    stage = snapshot.pipeline.phase.value
    overall = _overall_score_from_evaluation(_evaluation_from_snapshot(snapshot))
    cid = _candidate_id_from_snapshot(snapshot)
    if cid is None:
        raise ValueError("snapshot has no candidate StateLink")
    return {
        "candidate_id": str(cid),
        "stage": stage,
        "status": _status_block(stage),
        "overall_score": overall,
        "rank": None,
        "total_candidates": None,
        "available_actions": get_available_actions_for_phase(stage),
    }


def build_candidate_view(snapshot: OrchestrationState) -> Dict[str, Any]:
    """
    Compose a recruiter-facing dict from ``snapshot.extensions`` and pipeline phase.

    ``pipeline.phase`` (exposed as ``stage``) is the single source of truth for UI state;
    no secondary status layer is maintained beyond aggregate ``status.kind``.
    """
    stage = snapshot.pipeline.phase.value
    status = _status_block(stage)
    evaluation = _evaluation_from_snapshot(snapshot)
    profile = snapshot.ingress_profile
    return {
        "stage": stage,
        "status": status,
        "summary": _summary_from_snapshot(snapshot),
        "profile": None if profile is None else _model_dump_json(profile),
        "decision": _model_dump_json(snapshot.decision),
        "evaluation": None if evaluation is None else _model_dump_json(evaluation),
        "flags": _model_dump_json(snapshot.ingress_flags),
        "scores": _scores_section(evaluation),
        "ranking": _ranking_section(snapshot.extensions or {}),
        "next_actions": _next_actions_for_phase(stage),
    }


def get_state_summary(
    snapshot: OrchestrationState,
    *,
    store_revision: Optional[int],
) -> Dict[str, Any]:
    return {
        "pipeline_phase": snapshot.pipeline.phase.value,
        "transitions_count": len(snapshot.transitions),
        "state_id": str(snapshot.id),
        "store_revision": store_revision,
    }


def _timeline_catalog_note(runtime: ReadRuntime) -> Optional[str]:
    bus = runtime.bundle.bus
    rec = getattr(bus, "recorded_envelopes", None)
    if rec is None:
        return (
            "This bus implementation does not expose recorded_envelopes; merged catalog "
            "cannot include runtime-emitted publishes—ingress labels for nested orchestration "
            "runs may show as unknown types unless an explicit catalog is supplied elsewhere."
        )
    if len(rec) == 0:
        return "No envelopes recorded yet; publish events before expecting a rich timeline."
    return None


def get_timeline(runtime: ReadRuntime) -> Dict[str, Any]:
    return {
        "timeline_text": vertical_slice_timeline_text(runtime.bundle),
        "catalog_note": _timeline_catalog_note(runtime),
    }


def demo_skill_summaries(bundle: Any) -> Dict[str, Any]:
    hard: Optional[Dict[str, Any]] = None
    light: Optional[Dict[str, Any]] = None
    deep: Optional[Dict[str, Any]] = None
    got = bundle.store.get(bundle.state_id)
    snap = got.snapshot if got.ok and got.snapshot is not None else None
    for run in bundle.subscriber.run_history:
        if not run.ok:
            continue
        for sr in run.skill_results:
            name = sr.metadata.skill_name
            parts = skill_decision_summary_parts(sr, state_snapshot=snap)
            if name == SKILL_HARD_FILTER:
                hard = parts
            elif name == SKILL_LIGHT_SCORING:
                light = parts
            elif name == SKILL_DEEP_SCORING:
                deep = parts
    return {
        "hard_filter": hard,
        "light_scoring": light,
        "deep_scoring": deep,
    }


def get_demo_candidate(runtime: ReadRuntime) -> Dict[str, Any]:
    got = runtime.bundle.store.get(runtime.bundle.state_id)
    state_summary: Optional[Dict[str, Any]] = None
    phase: Optional[str] = None
    inactive_reason: Optional[str] = None
    if got.ok and got.snapshot is not None and got.meta is not None:
        phase = got.snapshot.pipeline.phase.value
        state_summary = get_state_summary(
            got.snapshot,
            store_revision=got.meta.store_revision,
        )
        inactive_reason = got.snapshot.extensions.get("inactive.reason")
    return {
        "candidate_id": str(runtime.candidate_id),
        "profile": dict(DEMO_CANDIDATE_DISPLAY),
        "pipeline_phase": phase,
        "state_summary": state_summary,
        "skill_summaries": demo_skill_summaries(runtime.bundle),
        "inactive_reason": inactive_reason,
    }


def _load_snapshot_for_candidate(runtime: ReadRuntime, candidate_id: UUID) -> OrchestrationState:
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None:
        raise CandidateNotFoundError(f"no orchestration state for candidate: {candidate_id!s}")
    return got.snapshot


def get_candidate_view_for_runtime(runtime: ReadRuntime, candidate_id: UUID) -> Dict[str, Any]:
    return build_candidate_view(_load_snapshot_for_candidate(runtime, candidate_id))


def get_state_summary_for_candidate(runtime: ReadRuntime, candidate_id: UUID) -> Dict[str, Any]:
    """Load state summary for ``candidate_id``; raises :class:`CandidateNotFoundError` when absent."""
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None or got.meta is None:
        raise CandidateNotFoundError(f"no orchestration state for candidate: {candidate_id!s}")
    return get_state_summary(got.snapshot, store_revision=got.meta.store_revision)


_TIMELINE_MULTI_CANDIDATE_MSG = "timeline not supported for multi-candidate yet"


def get_timeline_for_candidate(runtime: ReadRuntime, candidate_id: UUID) -> Dict[str, Any]:
    """
    Timeline for the wired default demo candidate only.

    Other candidate ids are rejected so global ``run_history`` does not leak cross-candidate data.
    """
    if candidate_id != runtime.candidate_id:
        raise CandidateNotFoundError(_TIMELINE_MULTI_CANDIDATE_MSG)
    _load_snapshot_for_candidate(runtime, candidate_id)
    return get_timeline(runtime)
