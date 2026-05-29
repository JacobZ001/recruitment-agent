"""
Canonical Candidate write helpers (R-009).

Applies vertical-slice skill outputs to the Candidate aggregate and builds
orchestration snapshot refs (no full evaluation/profile on snapshot).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple
from uuid import UUID

from interfaces.skill_interface import ExecutionStatus, SkillExecutionResult
from orchestrator.vertical_slice_planner import (
    SKILL_CV_PARSE_PROFILE,
    SKILL_CV_SCORE_LIGHT,
    SKILL_DEEP_SCORING,
    SKILL_HARD_FILTER,
    SKILL_LIGHT_SCORING,
    _deep_score_evaluation_from_skill_result,
    _hard_filter_evaluation_from_skill_result,
    _light_score_evaluation_from_skill_result,
)
from schemas.candidate_schema import (
    Candidate,
    CandidateProfile,
    DedupSignals,
    EvaluationStatus,
    Identity,
    SeniorityLevel,
    new_candidate,
)
from schemas.state_schema import (
    EvaluationState,
    EvaluationStatusRef,
    OrchestrationState,
)


def _model_copy_local(model: Any, **updates: Any) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=updates, deep=True)
    return model.copy(update=updates, deep=True)


def _normalize_email(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    s = value.strip().lower()
    return s or None


def _normalize_phone(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    digits = re.sub(r"\D", "", value)
    return digits or None


def cv_content_fingerprint(cv_text: str) -> str:
    normalized = " ".join(line.strip().lower() for line in cv_text.splitlines() if line.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _seniority_from_parse(value: Optional[str]) -> SeniorityLevel:
    if value == "junior":
        return SeniorityLevel.JUNIOR
    if value == "mid":
        return SeniorityLevel.MID
    if value == "senior":
        return SeniorityLevel.SENIOR
    return SeniorityLevel.UNKNOWN


def _ingress_to_candidate_profile(raw: Mapping[str, Any]) -> Tuple[CandidateProfile, Identity]:
    """Map parse skill ingress profile dict + optional identity fields to aggregate."""
    full_name = raw.get("full_name")
    headline = raw.get("headline")
    primary_email = raw.get("primary_email")
    primary_phone = raw.get("primary_phone")
    seniority_raw = raw.get("seniority")
    years = raw.get("years_experience")
    profile = CandidateProfile(
        headline=str(headline) if headline else None,
        summary=str(raw.get("summary") or ""),
        seniority=_seniority_from_parse(seniority_raw if isinstance(seniority_raw, str) else None),
        years_experience=float(years) if years is not None else None,
        skills=list(raw.get("skills") or []),
        industries=list(raw.get("industries") or []),
    )
    roles = list(raw.get("roles") or [])
    if roles and not profile.headline:
        profile = _model_copy_local(profile, headline=str(roles[0]))
    identity = Identity(
        full_name=str(full_name) if full_name else None,
        primary_email=str(primary_email) if primary_email else None,
        primary_phone=str(primary_phone) if primary_phone else None,
    )
    return profile, identity


def apply_skill_results_to_candidate(
    candidate: Candidate,
    skills: Sequence[Any],
    skill_results: Sequence[SkillExecutionResult],
    *,
    cv_text: Optional[str] = None,
    updated_by: str = "vertical_slice",
) -> Candidate:
    """Merge skill outputs into canonical Candidate (evaluation + profile)."""
    evaluation = (
        candidate.evaluation_status.model_copy(deep=True)
        if candidate.evaluation_status is not None
        else EvaluationStatus()
    )

    profile = candidate.profile
    identity = candidate.identity
    dedup = candidate.dedup_signals
    changed_eval = False
    changed_profile = False

    for spec, res in zip(skills, skill_results):
        if res.status not in (ExecutionStatus.SUCCEEDED, ExecutionStatus.PARTIAL_SUCCESS):
            continue
        if res.output is None:
            continue
        pl = res.output.payload or {}

        if spec.skill_name == SKILL_CV_PARSE_PROFILE:
            raw_profile = pl.get("profile")
            if isinstance(raw_profile, Mapping):
                profile, identity = _ingress_to_candidate_profile(raw_profile)
                changed_profile = True
            if cv_text:
                dedup = _model_copy_local(
                    dedup,
                    cv_content_fingerprint=cv_content_fingerprint(cv_text),
                )
            if identity.primary_email:
                dedup = _model_copy_local(
                    dedup, normalized_email=_normalize_email(identity.primary_email)
                )
            if identity.primary_phone:
                dedup = _model_copy_local(
                    dedup, normalized_phone=_normalize_phone(identity.primary_phone)
                )
            continue

        if spec.skill_name == SKILL_HARD_FILTER:
            hf = _hard_filter_evaluation_from_skill_result(res)
            if hf is not None:
                evaluation = _model_copy_local(evaluation, hard_filter=hf)
                changed_eval = True
            continue

        if spec.skill_name in (SKILL_LIGHT_SCORING, SKILL_CV_SCORE_LIGHT):
            light_eval = _light_score_evaluation_from_skill_result(res)
            if light_eval is not None:
                evaluation = _model_copy_local(evaluation, light=light_eval)
                changed_eval = True
            continue

        if spec.skill_name == SKILL_DEEP_SCORING:
            deep_eval = _deep_score_evaluation_from_skill_result(res)
            if deep_eval is not None:
                evaluation = _model_copy_local(evaluation, deep=deep_eval)
                changed_eval = True

    now = datetime.now(timezone.utc)
    meta = _model_copy_local(
        candidate.metadata,
        updated_at=now,
        updated_by=updated_by,
    )
    out = _model_copy_local(
        candidate,
        profile=profile if changed_profile else candidate.profile,
        identity=identity if changed_profile else candidate.identity,
        dedup_signals=dedup,
        metadata=meta,
    )
    if changed_eval:
        out = _model_copy_local(
            out,
            evaluation_status=evaluation,
            evaluation_revision=candidate.evaluation_revision + 1,
        )
    return out


def evaluation_status_ref_from_evaluation(
    evaluation: EvaluationState,
    *,
    revision: int,
) -> EvaluationStatusRef:
    score_type: Optional[str] = None
    overall: Optional[float] = None
    context_version: Optional[int] = None
    stale = False
    active = evaluation.deep or evaluation.light
    if evaluation.deep is not None:
        score_type = "deep"
        overall = float(evaluation.deep.normalized_score)
        context_version = int(evaluation.deep.context_version)
        stale = bool(evaluation.deep.stale)
    elif evaluation.light is not None:
        score_type = "light"
        overall = float(evaluation.light.normalized_score)
        context_version = int(evaluation.light.context_version)
        stale = bool(evaluation.light.stale)
    return EvaluationStatusRef(
        revision=revision,
        context_version=context_version,
        overall_score=overall,
        score_type=score_type,
        stale=stale,
    )


def finalize_orchestration_snapshot(
    snapshot: OrchestrationState,
    candidate: Candidate,
) -> OrchestrationState:
    """Set explicit ``candidate_id`` + ``evaluation_status_ref``; strip legacy snapshot-owned fields."""
    cid = candidate.candidate_id
    ref = evaluation_status_ref_from_evaluation(
        candidate.evaluation_status,
        revision=candidate.evaluation_revision,
    )
    return _model_copy_local(
        snapshot,
        candidate_id=cid,
        links=[],
        evaluation_status_ref=ref,
        ingress_profile=None,
        evaluation=None,
    )


def ensure_candidate_record(
    store: Any,
    candidate_id: UUID,
    *,
    occurred_at: Optional[datetime] = None,
    updated_by: str = "vertical_slice",
) -> Candidate:
    got = store.get(candidate_id)
    if got.ok and got.candidate is not None:
        return got.candidate
    cand = new_candidate(candidate_id, occurred_at=occurred_at, updated_by=updated_by)
    created = store.create(cand)
    if created.ok and created.candidate is not None:
        return created.candidate
    if (
        created.failure is not None
        and created.failure.code.value == "already_exists"
    ):
        retry = store.get(candidate_id)
        if retry.ok and retry.candidate is not None:
            return retry.candidate
    raise RuntimeError(f"candidate create failed: {created.failure}")


def find_candidate_ids_by_dedup_signals(
    store: Any,
    *,
    normalized_email: Optional[str] = None,
    normalized_phone: Optional[str] = None,
    cv_content_fingerprint: Optional[str] = None,
) -> List[UUID]:
    """Deterministic lookup helper (no auto-merge)."""
    matches: List[UUID] = []
    for cid in store.list_candidate_ids():
        got = store.get(cid)
        if not got.ok or got.candidate is None:
            continue
        sig = got.candidate.dedup_signals
        if normalized_email and sig.normalized_email == normalized_email:
            matches.append(cid)
            continue
        if normalized_phone and sig.normalized_phone == normalized_phone:
            matches.append(cid)
            continue
        if cv_content_fingerprint and sig.cv_content_fingerprint == cv_content_fingerprint:
            matches.append(cid)
    return matches


def evaluation_from_candidate(candidate: Candidate) -> EvaluationState:
    return candidate.evaluation_status
