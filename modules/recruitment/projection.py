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
from .candidate_sync import load_candidate_and_snapshot_for_read
from .candidate_writes import evaluation_from_candidate
from runtime.inspection import skill_decision_summary_parts
from schemas.candidate_schema import Candidate, SeniorityLevel
from schemas.state_schema import (
    EvaluationState,
    EvaluationStatusRef,
    OrchestrationState,
    PipelinePhase,
    ScoringContext,
)

from .exceptions import CandidateNotFoundError
from .policies import get_available_actions_for_phase

CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER = (
    "Not available (model-based evaluation under development)"
)

_RANKING_NOTE = "ranking not available in single-candidate mode"
_EMPTY_CRITERIA_LAYOUT: Tuple[Tuple[str, str], ...] = (
    ("communication", "universal"),
    ("ownership", "universal"),
    ("reliability", "universal"),
    ("thinking", "universal"),
    ("role_specific_fit", "role_specific"),
    ("recruiter_preference_alignment", "recruiter_preference"),
)


class ReadRuntime(Protocol):
    """Runtime surface for read-only projections."""

    @property
    def candidate_id(self) -> UUID: ...

    @property
    def bundle(self) -> Any: ...

    @property
    def candidate_store(self) -> Any: ...

    @property
    def scoring_context_store(self) -> Any: ...


def _recruiter_status_kind(phase: str) -> str:
    if phase == PipelinePhase.HIRED.value:
        return "hired"
    if phase == PipelinePhase.INACTIVE.value:
        return "inactive"
    return "active"


def _status_block(phase: str) -> Dict[str, Any]:
    return {"kind": _recruiter_status_kind(phase)}


def _model_dump_json(model: Any) -> Dict[str, Any]:
    return model.model_dump(mode="json")


def _evaluation_for_read(candidate: Candidate) -> Optional[EvaluationState]:
    ev = evaluation_from_candidate(candidate)
    if ev.light is not None or ev.deep is not None or ev.hard_filter is not None:
        return ev
    return None


def _overall_score_from_evaluation(evaluation: Optional[EvaluationState]) -> Dict[str, Any]:
    if evaluation is not None and evaluation.deep is not None:
        return {"value": float(evaluation.deep.normalized_score), "type": "deep"}
    if evaluation is not None and evaluation.light is not None:
        return {"value": float(evaluation.light.normalized_score), "type": "light"}
    ref = None  # caller may pass ref separately for list-only snapshots
    return {"value": None, "type": None}


def _overall_score_from_ref(ref: Optional[EvaluationStatusRef]) -> Dict[str, Any]:
    if ref is None or ref.overall_score is None:
        return {"value": None, "type": None}
    return {"value": float(ref.overall_score), "type": ref.score_type}


def _criteria_from_layout(evaluation: Optional[EvaluationState]) -> List[Dict[str, Any]]:
    light = evaluation.light if evaluation is not None else None
    if light is None:
        return [
            {
                "name": name,
                "score": None,
                "confidence": None,
                "source": source,
                "reason": None,
            }
            for name, source in _EMPTY_CRITERIA_LAYOUT
        ]
    out: List[Dict[str, Any]] = []
    layer_specs = (
        ("universal", light.l1_universal.criteria),
        ("role_specific", light.l2_role_specific.criteria),
        ("recruiter_preference", light.l3_recruiter_preference.criteria),
    )
    for source, criteria in layer_specs:
        for name, item in criteria.items():
            out.append(
                {
                    "name": name,
                    "score": float(item.score),
                    "confidence": float(item.confidence),
                    "source": source,
                    "reason": item.reason,
                }
            )
    return out


def _scores_section(evaluation: Optional[EvaluationState]) -> Dict[str, Any]:
    active = None
    if evaluation is not None:
        active = evaluation.deep or evaluation.light
    return {
        "criteria": _criteria_from_layout(evaluation),
        "overall_score": _overall_score_from_evaluation(evaluation),
        "context_version": None if active is None else int(active.context_version),
        "stale": None if active is None else bool(active.stale),
    }


def _ranking_section(_ext: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "rank": None,
        "total_candidates": None,
        "note": _RANKING_NOTE,
    }


def _available_actions_for_snapshot(snapshot: OrchestrationState) -> List[Dict[str, Any]]:
    return get_available_actions_for_phase(
        snapshot.pipeline.phase.value,
        transition_extensions=dict(snapshot.extensions or {}),
    )


def _next_actions_from_available_actions(actions: List[Dict[str, Any]]) -> List[str]:
    return [str(item["label"]) for item in actions]


def _candidate_id_from_snapshot(snapshot: OrchestrationState) -> Optional[UUID]:
    if snapshot.candidate_id is not None:
        return snapshot.candidate_id
    for link in snapshot.links:
        if link.kind.strip().lower() == "candidate":
            return link.id
    return None


def _list_headline(candidate: Optional[Candidate]) -> str:
    if candidate is None:
        return ""
    if candidate.profile.headline:
        return candidate.profile.headline
    if candidate.identity.full_name:
        return candidate.identity.full_name
    return ""


def _profile_dto(candidate: Candidate) -> Dict[str, Any]:
    prof = candidate.profile
    ident = candidate.identity
    sen = prof.seniority.value if prof.seniority != SeniorityLevel.UNKNOWN else None
    return {
        "full_name": ident.full_name,
        "primary_email": ident.primary_email,
        "primary_phone": ident.primary_phone,
        "preferred_contact_method": (
            ident.preferred_contact_method.value if ident.preferred_contact_method else None
        ),
        "location": ident.location,
        "timezone": ident.timezone,
        "external_profile_urls": list(ident.external_profile_urls),
        "headline": prof.headline,
        "summary": prof.summary or "",
        "seniority": sen,
        "years_experience": prof.years_experience,
        "languages": list(prof.languages),
        "skills": list(prof.skills),
        "industries": list(prof.industries),
        "work_authorization": prof.work_authorization.value,
        "compensation_expectation": prof.compensation_expectation,
        "availability_date": (
            prof.availability_date.isoformat() if prof.availability_date else None
        ),
        "roles": [prof.headline] if prof.headline else [],
        "extensions": {},
    }


def _summary_text(candidate: Candidate) -> str:
    if candidate.profile.summary and candidate.profile.summary.strip():
        return candidate.profile.summary
    return CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER


def build_candidate_list_item(
    snapshot: OrchestrationState,
    *,
    candidate: Candidate,
) -> Dict[str, Any]:
    stage = snapshot.pipeline.phase.value
    evaluation = _evaluation_for_read(candidate)
    overall = _overall_score_from_evaluation(evaluation)
    if overall["value"] is None and snapshot.evaluation_status_ref is not None:
        overall = _overall_score_from_ref(snapshot.evaluation_status_ref)
    cid = _candidate_id_from_snapshot(snapshot)
    if cid is None:
        raise ValueError("snapshot has no candidate id")
    summary = candidate.profile.summary or ""
    top_skills = list(candidate.profile.skills[:6])
    full_name = candidate.identity.full_name or ""
    return {
        "candidate_id": str(cid),
        "full_name": full_name,
        "stage": stage,
        "status": _status_block(stage),
        "headline": _list_headline(candidate),
        "summary": summary,
        "top_skills": top_skills,
        "overall_score": overall,
        "rank": None,
        "total_candidates": None,
        "available_actions": _available_actions_for_snapshot(snapshot),
    }


def _scoring_context_summary(active_scoring_context: Optional[ScoringContext]) -> Optional[Dict[str, Any]]:
    if active_scoring_context is None:
        return None
    org = active_scoring_context.organization_context
    recruiter = active_scoring_context.recruiter_actor_context
    job = active_scoring_context.job_context
    return {
        "context_version": int(active_scoring_context.context_version),
        "status": active_scoring_context.status.value,
        "organization": None if org is None else org.company_name,
        "recruiter_actor_id": None if recruiter is None else recruiter.actor_id,
        "job_title": None if job is None else job.title,
    }


def build_candidate_view(
    snapshot: OrchestrationState,
    *,
    candidate: Candidate,
    active_scoring_context: Optional[ScoringContext] = None,
) -> Dict[str, Any]:
    stage = snapshot.pipeline.phase.value
    status = _status_block(stage)
    evaluation = _evaluation_for_read(candidate)
    available_actions = _available_actions_for_snapshot(snapshot)
    return {
        "stage": stage,
        "status": status,
        "summary": _summary_text(candidate),
        "profile": _profile_dto(candidate),
        "decision": _model_dump_json(snapshot.decision),
        "evaluation": None if evaluation is None else _model_dump_json(evaluation),
        "scoring_context": _scoring_context_summary(active_scoring_context),
        "flags": _model_dump_json(snapshot.ingress_flags),
        "scores": _scores_section(evaluation),
        "ranking": _ranking_section(snapshot.extensions or {}),
        "available_actions": available_actions,
        "next_actions": _next_actions_from_available_actions(available_actions),
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
    candidate, snapshot = load_candidate_and_snapshot_for_read(runtime, candidate_id)
    return build_candidate_view(
        snapshot,
        candidate=candidate,
        active_scoring_context=runtime.scoring_context_store.get(),
    )


def get_state_summary_for_candidate(runtime: ReadRuntime, candidate_id: UUID) -> Dict[str, Any]:
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None or got.meta is None:
        raise CandidateNotFoundError(f"no orchestration state for candidate: {candidate_id!s}")
    return get_state_summary(got.snapshot, store_revision=got.meta.store_revision)


_TIMELINE_MULTI_CANDIDATE_MSG = "timeline not supported for multi-candidate yet"


def get_timeline_for_candidate(runtime: ReadRuntime, candidate_id: UUID) -> Dict[str, Any]:
    if candidate_id != runtime.candidate_id:
        raise CandidateNotFoundError(_TIMELINE_MULTI_CANDIDATE_MSG)
    _load_snapshot_for_candidate(runtime, candidate_id)
    return get_timeline(runtime)
