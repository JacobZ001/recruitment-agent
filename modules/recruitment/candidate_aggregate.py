"""
Canonical Candidate aggregate writes and orchestration dual-write (R-009 / R-011.1).

Skill merge, snapshot finalize, ensure-record helpers, and bounded snapshot reconciliation.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Protocol, Sequence, Tuple
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


# --- Orchestration dual-write (formerly candidate_sync) ---

logger = logging.getLogger(__name__)

SNAPSHOT_RECONCILE_MAX_ATTEMPTS = 3

SYNC_PENDING_SNAPSHOT_RECONCILE = "sync.pending_snapshot_reconcile"
SYNC_LAST_OUTCOME = "sync.last_dual_write_outcome"


class DualWriteErrorCode(str, Enum):
    CANDIDATE_REPLACE_FAILED = "candidate_replace_failed"
    SNAPSHOT_REPLACE_FAILED_AFTER_CANDIDATE = "snapshot_replace_failed_after_candidate_success"
    RECONCILIATION_SUCCEEDED = "reconciliation_succeeded"
    RECONCILIATION_FAILED = "reconciliation_failed"


@dataclass(frozen=True)
class PersistDualWriteOutcome:
    ok: bool
    error_code: Optional[str] = None
    message: str = ""
    reconciliation_attempted: bool = False
    reconciliation_succeeded: bool = False
    candidate_revision: Optional[int] = None


class _OrchestrationStore(Protocol):
    def get(self, state_id: UUID) -> Any: ...
    def get_for_candidate(self, candidate_id: UUID) -> Any: ...
    def replace(
        self,
        state_id: UUID,
        snapshot: OrchestrationState,
        *,
        expected_store_revision: int,
    ) -> Any: ...


class _CandidateStore(Protocol):
    def get(self, candidate_id: UUID) -> Any: ...
    def replace(self, candidate: Candidate, *, expected_store_revision: int) -> Any: ...


def evaluation_ref_lags_candidate(
    snapshot: OrchestrationState,
    candidate: Candidate,
) -> bool:
    ref = snapshot.evaluation_status_ref
    ref_rev = int(ref.revision) if ref is not None else -1
    return int(candidate.evaluation_revision) > ref_rev


def _mark_candidate_pending_reconcile(
    candidate: Candidate,
    *,
    state_id: UUID,
    outcome_code: str,
) -> Candidate:
    sync = dict(candidate.extensions.get("sync") or {})
    sync[SYNC_PENDING_SNAPSHOT_RECONCILE] = True
    sync["state_id"] = str(state_id)
    sync[SYNC_LAST_OUTCOME] = outcome_code
    return candidate.model_copy(update={"extensions": {**candidate.extensions, "sync": sync}})


def persist_candidate_and_snapshot_with_reconcile(
    *,
    candidate_store: _CandidateStore,
    orchestration_store: _OrchestrationStore,
    state_id: UUID,
    candidate_id: UUID,
    workflow_snapshot: OrchestrationState,
    candidate: Candidate,
    expected_snapshot_revision: int,
) -> PersistDualWriteOutcome:
    """Replace canonical Candidate then orchestration snapshot; reconcile on snapshot failure."""
    got_c = candidate_store.get(candidate_id)
    if not got_c.ok or got_c.meta is None:
        return PersistDualWriteOutcome(
            ok=False,
            error_code=DualWriteErrorCode.CANDIDATE_REPLACE_FAILED.value,
            message=f"candidate store get failed before replace: {got_c.failure}",
        )
    rep_c = candidate_store.replace(candidate, expected_store_revision=got_c.meta.store_revision)
    if not rep_c.ok or rep_c.candidate is None:
        logger.warning(
            "dual_write candidate_replace_failed candidate_id=%s failure=%s",
            candidate_id,
            rep_c.failure,
        )
        return PersistDualWriteOutcome(
            ok=False,
            error_code=DualWriteErrorCode.CANDIDATE_REPLACE_FAILED.value,
            message=f"candidate store replace failed: {rep_c.failure}",
        )
    cand = rep_c.candidate
    snap = finalize_orchestration_snapshot(workflow_snapshot, cand)

    for attempt in range(1, SNAPSHOT_RECONCILE_MAX_ATTEMPTS + 1):
        rep_s = orchestration_store.replace(
            state_id,
            snap,
            expected_store_revision=expected_snapshot_revision,
        )
        if rep_s.ok:
            logger.info(
                "dual_write snapshot_replace_ok candidate_id=%s state_id=%s attempt=%s",
                candidate_id,
                state_id,
                attempt,
            )
            return PersistDualWriteOutcome(
                ok=True,
                candidate_revision=cand.evaluation_revision,
            )
        logger.warning(
            "dual_write snapshot_replace_failed candidate_id=%s state_id=%s attempt=%s failure=%s",
            candidate_id,
            state_id,
            attempt,
            rep_s.failure,
        )
        got_s = orchestration_store.get(state_id)
        if got_s.ok and got_s.meta is not None:
            expected_snapshot_revision = got_s.meta.store_revision
        snap = finalize_orchestration_snapshot(workflow_snapshot, cand)

    logger.warning(
        "dual_write reconciliation_failed candidate_id=%s state_id=%s after candidate success",
        candidate_id,
        state_id,
    )
    cand = _mark_candidate_pending_reconcile(
        cand,
        state_id=state_id,
        outcome_code=DualWriteErrorCode.RECONCILIATION_FAILED.value,
    )
    got_c2 = candidate_store.get(candidate_id)
    if got_c2.ok and got_c2.meta is not None:
        candidate_store.replace(cand, expected_store_revision=got_c2.meta.store_revision)

    return PersistDualWriteOutcome(
        ok=False,
        error_code=DualWriteErrorCode.SNAPSHOT_REPLACE_FAILED_AFTER_CANDIDATE.value,
        message="state store replace failed after candidate success; reconciliation exhausted",
        reconciliation_attempted=True,
        reconciliation_succeeded=False,
        candidate_revision=cand.evaluation_revision,
    )
