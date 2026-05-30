"""
Recruitment application use cases (ingress publish, demo sequence).

Runtime is always passed in by the API layer; this module does not construct runtimes.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Dict, List, Optional, Protocol, Sequence, Tuple
from uuid import UUID, uuid4

from interfaces.skill_interface import (
    ExecutionContext,
    ExecutionStatus,
    FailureCategory,
    SkillInputEnvelope,
)
from interfaces.event_bus_interface import DeliveryStatus
from runtime.in_memory_state_store import StateStoreFailureCode
from .state_init import initial_orchestration_state
from .ingress import FIXED_CLOCK as _FIXED_CLOCK
from .ingress import build_ingress_envelope as _envelope
from schemas.candidate_schema import Candidate, new_candidate
from schemas.state_schema import OrchestrationState

from . import policies
from .exceptions import (
    CandidateNotFoundError,
    DemoRunPreconditionError,
    DuplicateCandidateHighConfidenceError,
    InvalidDedupGovernanceError,
    IdempotencyKeyConflictError,
    IdempotencyKeyInProgressError,
    IdempotencyKeyRequiredError,
    IdempotencyReplayError,
    InvalidCandidateActionError,
    InvalidIngressEventError,
    InvalidRecruiterActionPayloadError,
    InvalidScoringContextError,
    ScoringContextNotReadyError,
    ScoringFailedError,
)
from .dedup import (
    DedupEvaluation,
    DedupMatch,
    DedupOutcome,
    dedup_matches_json_normalized,
    dedup_matches_to_json,
    evaluate_dedup_fingerprint_suspected_from_ingress_signals,
    evaluate_dedup_high_confidence_from_ingress_signals,
    extract_ingress_signals_from_cv_text,
    governance_flags_from_candidate,
    ingress_signals_from_candidate,
    merge_dedup_matches,
)
from .ingress_governance import (
    IngressGovernanceFlags,
    ingress_governance_by_candidate_id,
)
from .idempotency_store import (
    IDEMPOTENCY_METHOD_PATH,
    IdempotencyRecordStatus,
)
from .pdf_ingest import decode_pdf_base64, extract_text_from_pdf_bytes
from .projection import (
    SYNC_PENDING_SNAPSHOT_RECONCILE,
    build_candidate_list_item,
    finalize_orchestration_snapshot,
    get_state_summary,
)
from .projection import get_candidate_view_for_runtime as _projection_candidate_view
from .scoring_context_service import (
    clear_evaluation_stale_flags_on_candidate,
    clear_job_from_scoring_context,
    clear_organization_from_scoring_context,
    clear_recruiter_actor_from_scoring_context,
    compute_scoring_context_materialization_blockers,
    finalize_ready_context_with_fingerprint,
    force_mark_evaluations_stale_on_candidate,
    job_context_to_authoring_text,
    mark_evaluation_stale,
    organization_context_to_authoring_text,
    recruiter_actor_context_to_authoring_text,
    recruiter_answers_to_job_authoring_text,
    refresh_scoring_context,
    scoring_context_is_ready,
    update_scoring_context,
)
from schemas.state_schema import (
    EvaluationState,
    JobContext,
    OrchestrationState,
    OrganizationContext,
    RecruiterActorContext,
    ScoringContext,
    ScoringContextStatus,
)
from skills.llm.scoring_context_materialize_from_prose import (
    ScoringContextMaterializeFromProseSkill,
)

DEFAULT_RECRUITER_ACTION_GOVERNANCE_PAYLOAD: Dict[str, Any] = {
    "actor_id": "recruitment-api",
    "actor_type": "recruiter",
    "reason": "Recruiter action via candidate workflow API",
    "evidence_refs": [],
}
from .registry import get_state_id


class IngressRuntime(Protocol):
    """Runtime surface required for ingress and demo use cases."""

    @property
    def candidate_id(self) -> UUID: ...

    @property
    def bundle(self) -> Any: ...

    @property
    def candidate_store(self) -> Any: ...

    @property
    def scoring_context_store(self) -> Any: ...

    @property
    def idempotency_store(self) -> Any: ...

    def begin_idempotency_operation(self, idempotency_key: str) -> None: ...

    def end_idempotency_operation(self, idempotency_key: str) -> None: ...

    def next_publish_sequence(self) -> int: ...

    def run_primary_demo_sequence(self) -> OrchestrationState: ...


@dataclass(frozen=True)
class EventIngressResult:
    ingress_accepted: bool
    publish_status: str
    event_id: str
    event_type: str
    publish_result: Dict[str, Any]
    state_summary: Optional[Dict[str, Any]]


@dataclass(frozen=True)
class CandidatePdfIngressResult:
    candidate_id: UUID
    ingress_accepted: bool
    publish_status: str
    event_id: str
    event_type: str
    publish_result: Dict[str, Any]
    state_summary: Optional[Dict[str, Any]]
    dedup: Optional[Dict[str, Any]] = None


def _model_copy_local(model: Any, **updates: Any) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=updates, deep=True)
    return model.copy(update=updates, deep=True)


def _model_dump_json(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def get_active_scoring_context(runtime: IngressRuntime) -> Optional[ScoringContext]:
    return runtime.scoring_context_store.get()


def _persist_scoring_context(runtime: IngressRuntime, context: ScoringContext) -> ScoringContext:
    return runtime.scoring_context_store.replace(context)


def _materialization_input_text(current: Optional[str], fallback: Optional[str]) -> str:
    text = str(current or "").strip()
    if text:
        return text
    return str(fallback or "").strip()


def _refresh_materialized_context_from_prose(
    runtime: IngressRuntime,
    current: Optional[ScoringContext],
    *,
    materializer: Optional[ScoringContextMaterializeFromProseSkill] = None,
) -> ScoringContext:
    base = current or ScoringContext()
    organization_text = _materialization_input_text(
        base.organization_authoring_text,
        organization_context_to_authoring_text(base.organization_context)
        if base.organization_context is not None
        else None,
    )
    recruiter_text = _materialization_input_text(
        base.recruiter_actor_authoring_text,
        recruiter_actor_context_to_authoring_text(base.recruiter_actor_context)
        if base.recruiter_actor_context is not None
        else None,
    )
    job_text = _materialization_input_text(
        base.job_authoring_text,
        job_context_to_authoring_text(base.job_context) if base.job_context is not None else None,
    )
    if not organization_text or not recruiter_text or not job_text:
        raise InvalidScoringContextError(
            "scoring_context cannot become ready until organization, recruiter, and job prose "
            "authoring inputs are all present"
        )
    skill = materializer or ScoringContextMaterializeFromProseSkill()
    result = skill.execute(
        SkillInputEnvelope(
            payload={
                "vertical_slice.planner_path": "scoring_context_refresh",
                "organization_authoring_text": organization_text,
                "recruiter_actor_authoring_text": recruiter_text,
                "job_authoring_text": job_text,
            }
        ),
        ExecutionContext(
            run_reason="scoring_context_refresh",
            subject_kind="scoring_context",
            actor_id="recruitment-api",
        ),
    )
    if result.status != ExecutionStatus.SUCCEEDED or result.output is None:
        failure = result.failure
        if failure is not None and failure.category == FailureCategory.VALIDATION_ERROR:
            raise InvalidScoringContextError(str(failure.message))
        raise ScoringFailedError("scoring_context_materialization_failed")
    payload = result.output.payload or {}
    try:
        if hasattr(OrganizationContext, "model_validate"):
            organization_context = OrganizationContext.model_validate(payload.get("organization_context") or {})
            recruiter_actor_context = RecruiterActorContext.model_validate(
                payload.get("recruiter_actor_context") or {}
            )
            job_context = JobContext.model_validate(payload.get("job_context") or {})
        else:
            organization_context = OrganizationContext.parse_obj(payload.get("organization_context") or {})
            recruiter_actor_context = RecruiterActorContext.parse_obj(
                payload.get("recruiter_actor_context") or {}
            )
            job_context = JobContext.parse_obj(payload.get("job_context") or {})
    except Exception as exc:
        raise InvalidScoringContextError(
            f"invalid materialized scoring_context payload: {exc}"
        ) from exc
    return refresh_scoring_context(
        base,
        organization_context=organization_context,
        recruiter_actor_context=recruiter_actor_context,
        job_context=job_context,
        derived_l2_criteria=list(payload.get("derived_l2_criteria") or []),
        derived_l3_criteria=list(payload.get("derived_l3_criteria") or []),
    )


def _context_was_ready(context: Optional[ScoringContext]) -> bool:
    return context is not None and context.status == ScoringContextStatus.READY


def force_mark_all_candidate_evaluations_stale(runtime: IngressRuntime) -> None:
    """Mark every candidate light/deep evaluation stale (R-014 edit from ready)."""
    cand_store = runtime.candidate_store
    ostore = runtime.bundle.store
    for cid in cand_store.list_candidate_ids():
        got_c = cand_store.get(cid)
        if not got_c.ok or got_c.candidate is None or got_c.meta is None:
            continue
        evaluation = got_c.candidate.evaluation_status
        if evaluation is None:
            continue
        next_evaluation = force_mark_evaluations_stale_on_candidate(evaluation)
        if next_evaluation is evaluation:
            continue
        next_cand = _model_copy_local(
            got_c.candidate,
            evaluation_status=next_evaluation,
            evaluation_revision=got_c.candidate.evaluation_revision + 1,
        )
        rep_c = cand_store.replace(next_cand, expected_store_revision=got_c.meta.store_revision)
        if not rep_c.ok or rep_c.candidate is None:
            continue
        got_s = ostore.get_for_candidate(cid)
        if not got_s.ok or got_s.snapshot is None or got_s.meta is None:
            continue
        snap = finalize_orchestration_snapshot(got_s.snapshot, rep_c.candidate)
        ostore.replace(
            got_s.meta.state_id,
            snap,
            expected_store_revision=got_s.meta.store_revision,
        )


def clear_all_candidate_evaluation_stale_flags(runtime: IngressRuntime) -> None:
    """Clear evaluation stale after idempotent re-ready (R-014)."""
    cand_store = runtime.candidate_store
    ostore = runtime.bundle.store
    for cid in cand_store.list_candidate_ids():
        got_c = cand_store.get(cid)
        if not got_c.ok or got_c.candidate is None or got_c.meta is None:
            continue
        evaluation = got_c.candidate.evaluation_status
        if evaluation is None:
            continue
        next_evaluation = clear_evaluation_stale_flags_on_candidate(evaluation)
        if next_evaluation is evaluation:
            continue
        next_cand = _model_copy_local(
            got_c.candidate,
            evaluation_status=next_evaluation,
            evaluation_revision=got_c.candidate.evaluation_revision + 1,
        )
        rep_c = cand_store.replace(next_cand, expected_store_revision=got_c.meta.store_revision)
        if not rep_c.ok or rep_c.candidate is None:
            continue
        got_s = ostore.get_for_candidate(cid)
        if not got_s.ok or got_s.snapshot is None or got_s.meta is None:
            continue
        snap = finalize_orchestration_snapshot(got_s.snapshot, rep_c.candidate)
        ostore.replace(
            got_s.meta.state_id,
            snap,
            expected_store_revision=got_s.meta.store_revision,
        )


def _mark_existing_candidate_evaluations_stale(
    runtime: IngressRuntime, *, active_context_version: int
) -> None:
    cand_store = runtime.candidate_store
    ostore = runtime.bundle.store
    for cid in cand_store.list_candidate_ids():
        got_c = cand_store.get(cid)
        if not got_c.ok or got_c.candidate is None or got_c.meta is None:
            continue
        evaluation = got_c.candidate.evaluation_status
        if evaluation is None:
            continue
        next_light = mark_evaluation_stale(
            evaluation.light, active_context_version=active_context_version
        )
        next_deep = mark_evaluation_stale(
            evaluation.deep, active_context_version=active_context_version
        )
        if next_light is evaluation.light and next_deep is evaluation.deep:
            continue
        next_evaluation = _model_copy_local(
            evaluation,
            light=next_light,
            deep=next_deep,
        )
        next_cand = _model_copy_local(
            got_c.candidate,
            evaluation_status=next_evaluation,
            evaluation_revision=got_c.candidate.evaluation_revision + 1,
        )
        rep_c = cand_store.replace(next_cand, expected_store_revision=got_c.meta.store_revision)
        if not rep_c.ok or rep_c.candidate is None:
            continue
        got_s = ostore.get_for_candidate(cid)
        if not got_s.ok or got_s.snapshot is None or got_s.meta is None:
            continue
        snap = finalize_orchestration_snapshot(got_s.snapshot, rep_c.candidate)
        ostore.replace(
            got_s.meta.state_id,
            snap,
            expected_store_revision=got_s.meta.store_revision,
        )


def _require_ready_scoring_context(runtime: IngressRuntime) -> ScoringContext:
    context = get_active_scoring_context(runtime)
    if context is None:
        raise ScoringContextNotReadyError("scoring_context_not_ready: no active scoring_context")
    if not scoring_context_is_ready(context):
        raise ScoringContextNotReadyError(
            f"scoring_context_not_ready: active scoring_context status is {context.status.value}"
        )
    return context


def author_organization_context(
    runtime: IngressRuntime,
    context: OrganizationContext,
) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = update_scoring_context(
        current,
        organization_authoring_text=organization_context_to_authoring_text(context),
        organization_context=context,
        source_refs=context.source_refs,
    )
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def author_recruiter_actor_context(
    runtime: IngressRuntime,
    context: RecruiterActorContext,
) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = update_scoring_context(
        current,
        recruiter_actor_authoring_text=recruiter_actor_context_to_authoring_text(context),
        recruiter_actor_context=context,
        source_refs=context.source_refs,
    )
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def author_job_context(
    runtime: IngressRuntime,
    context: JobContext,
) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = update_scoring_context(
        current,
        job_authoring_text=job_context_to_authoring_text(context),
        job_context=context,
        source_refs=context.source_refs,
    )
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def author_organization_context_from_text(
    runtime: IngressRuntime,
    raw_text: str,
    *,
    source_ref: Optional[str] = None,
) -> ScoringContext:
    text = str(raw_text or "").strip()
    if not text:
        raise InvalidScoringContextError("organization_context text must be non-empty")
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = update_scoring_context(
        current,
        organization_authoring_text=text,
        source_refs=[source_ref] if source_ref else None,
    )
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def author_recruiter_actor_context_from_text(
    runtime: IngressRuntime,
    raw_text: str,
    *,
    source_ref: Optional[str] = None,
) -> ScoringContext:
    text = str(raw_text or "").strip()
    if not text:
        raise InvalidScoringContextError("recruiter_actor_context text must be non-empty")
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = update_scoring_context(
        current,
        recruiter_actor_authoring_text=text,
        source_refs=[source_ref] if source_ref else None,
    )
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def author_job_context_from_text(
    runtime: IngressRuntime,
    raw_text: str,
    *,
    source_ref: Optional[str] = None,
) -> ScoringContext:
    text = str(raw_text or "").strip()
    if not text:
        raise InvalidScoringContextError("job_context text must be non-empty")
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = update_scoring_context(
        current,
        job_authoring_text=text,
        source_refs=[source_ref] if source_ref else None,
    )
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def author_job_context_from_pdf(
    runtime: IngressRuntime,
    pdf_base64: str,
    *,
    file_name: str = "job_context.pdf",
) -> ScoringContext:
    pdf_bytes = decode_pdf_base64(pdf_base64, file_name=file_name)
    extracted = extract_text_from_pdf_bytes(pdf_bytes, file_name=file_name)
    return author_job_context_from_text(
        runtime,
        extracted.cv_text,
        source_ref=f"pdf://{extracted.file_name}",
    )


def author_job_context_from_recruiter_answers(
    runtime: IngressRuntime,
    *,
    role_title: str,
    must_haves_answer: str,
    preferred_answer: str,
    success_answer: str,
    responsibilities_answer: str,
) -> ScoringContext:
    if not str(role_title or "").strip():
        raise InvalidScoringContextError("role_title must be non-empty")
    return author_job_context_from_text(
        runtime,
        recruiter_answers_to_job_authoring_text(
            role_title=role_title,
            must_haves_answer=must_haves_answer,
            preferred_answer=preferred_answer,
            success_answer=success_answer,
            responsibilities_answer=responsibilities_answer,
        ),
        source_ref="normalized://recruiter_answers/job_context",
    )


def refresh_active_scoring_context(
    runtime: IngressRuntime,
    *,
    materializer: Optional[ScoringContextMaterializeFromProseSkill] = None,
) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    prev_fp = current.last_ready_materialized_fingerprint if current is not None else None
    refreshed = _refresh_materialized_context_from_prose(
        runtime,
        current,
        materializer=materializer,
    )
    if refreshed.status != ScoringContextStatus.READY:
        blockers = compute_scoring_context_materialization_blockers(refreshed)
        detail = (
            "scoring_context cannot become ready until prose authoring is normalized into "
            "typed context and materialized L2/L3 criteria succeed"
        )
        if blockers:
            detail = f"{detail}; blockers: {'; '.join(blockers)}"
        raise InvalidScoringContextError(detail)
    finalized = finalize_ready_context_with_fingerprint(current, refreshed)
    persisted = _persist_scoring_context(runtime, finalized)
    new_fp = persisted.last_ready_materialized_fingerprint
    if prev_fp is not None and new_fp == prev_fp:
        clear_all_candidate_evaluation_stale_flags(runtime)
    elif prev_fp is not None and new_fp != prev_fp:
        _mark_existing_candidate_evaluations_stale(
            runtime, active_context_version=persisted.context_version
        )
    return persisted


def _ensure_demo_scoring_context_ready(runtime: IngressRuntime) -> None:
    current = get_active_scoring_context(runtime)
    if current is not None and scoring_context_is_ready(current):
        return
    author_organization_context(
        runtime,
        OrganizationContext(
            company_name="BlueOcean Demo",
            industry="recruitment",
            team_name="Demo Talent Ops",
            environment_signals=["high-visibility recruiter operations"],
            preference_signals=["clear communication"],
            summary="Deterministic demo scoring context.",
            source_refs=["demo://organization"],
        ),
    )
    author_recruiter_actor_context(
        runtime,
        RecruiterActorContext(
            actor_id="demo-recruiter",
            actor_role="demo_operator",
            preference_signals=["ownership"],
            avoid_signals=["unclear updates"],
            summary="Deterministic demo recruiter context.",
            source_refs=["demo://recruiter"],
        ),
    )
    author_job_context_from_recruiter_answers(
        runtime,
        role_title="Demo Recruiting Operations Specialist",
        must_haves_answer="stakeholder communication\nprocess ownership",
        preferred_answer="ATS familiarity",
        success_answer="keep candidate flow organized",
        responsibilities_answer="coordinate interviews\nsurface blockers early",
    )
    refresh_active_scoring_context(runtime)


def _ensure_candidate_state(runtime: IngressRuntime, candidate_id: UUID) -> UUID:
    """
    Write path only: ensure a store snapshot exists for ``candidate_id`` before ingress publish.

    Uses deterministic ``state_id``; does not register candidates in memory.
    """
    state_id = get_state_id(candidate_id)
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if got.ok and got.snapshot is not None:
        return state_id

    init = initial_orchestration_state(
        state_id=state_id,
        candidate_id=candidate_id,
        occurred_at=_FIXED_CLOCK,
    )
    ensure_candidate_record(runtime.candidate_store, candidate_id, occurred_at=_FIXED_CLOCK)
    created = runtime.bundle.store.create(init)
    if created.ok:
        return state_id
    if (
        created.failure is not None
        and created.failure.code == StateStoreFailureCode.ALREADY_EXISTS
    ):
        return state_id
    raise RuntimeError(f"candidate state create failed: {created.failure}")


def _state_summary_after_publish(
    runtime: IngressRuntime, *, candidate_id: UUID
) -> Optional[Dict[str, Any]]:
    cur = runtime.bundle.store.get_for_candidate(candidate_id)
    if cur.ok and cur.snapshot is not None and cur.meta is not None:
        return get_state_summary(cur.snapshot, store_revision=cur.meta.store_revision)
    return None


def publish_ingress_event(
    runtime: IngressRuntime,
    candidate_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
    *,
    correlation_id: Optional[UUID] = None,
) -> EventIngressResult:
    """Publish one allowed ingress envelope onto the runtime bus.

    Governance payloads are not merged with bootstrap/api_sequence fields.
    """
    if not policies.is_allowed_ingress_event(event_type):
        raise InvalidIngressEventError(f"event_type not allowed: {event_type!r}")

    scoring_context: Optional[ScoringContext] = None
    if event_type in ("cv_submitted", "deep_scoring_completed"):
        scoring_context = _require_ready_scoring_context(runtime)

    _ensure_candidate_state(runtime, candidate_id)
    seq = runtime.next_publish_sequence()
    corr = correlation_id if correlation_id is not None else candidate_id

    env = _envelope(
        event_type=event_type,
        candidate_id=candidate_id,
        correlation_id=corr,
        occurred_at=_FIXED_CLOCK,
        seq=seq,
    )
    if policies.is_governance_event(event_type):
        merged_payload = dict(payload)
    else:
        merged_payload = policies.merge_non_governance_publish_payload(
            dict(env.payload), payload, seq=seq
        )
        if event_type in ("cv_submitted", "deep_scoring_completed") and scoring_context is not None:
            merged_payload["scoring_context"] = _model_dump_json(scoring_context)
    env = env.model_copy(update={"payload": merged_payload})

    pr = runtime.bundle.bus.publish(env)
    if event_type == "cv_submitted" and pr.status != DeliveryStatus.ACCEPTED:
        raise ScoringFailedError("scoring_failed")
    pub_dump = pr.model_dump(mode="json")

    return EventIngressResult(
        ingress_accepted=pr.status == DeliveryStatus.ACCEPTED,
        publish_status=pr.status.value,
        event_id=str(env.event_id),
        event_type=env.event_type,
        publish_result=pub_dump,
        state_summary=_state_summary_after_publish(runtime, candidate_id=candidate_id),
    )


def publish_recruitment_event(
    runtime: IngressRuntime,
    candidate_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
    *,
    correlation_id: Optional[UUID] = None,
) -> EventIngressResult:
    """Publish a non-governance pipeline ingress event (system progression / CV path)."""
    if policies.is_governance_event(event_type):
        raise InvalidIngressEventError(
            f"event_type {event_type!r} is governance; use record_recruiter_decision"
        )
    return publish_ingress_event(
        runtime,
        candidate_id,
        event_type,
        payload,
        correlation_id=correlation_id,
    )


def submit_cv(
    runtime: IngressRuntime,
    candidate_id: UUID,
    cv_text: str,
    *,
    correlation_id: Optional[UUID] = None,
) -> EventIngressResult:
    """
    Ingest raw CV text for a candidate (single ``cv_submitted`` event).

    Triggers LLM parse-and-score; results persist on typed snapshot profile/evaluation fields.
    """
    text = cv_text.strip()
    if not text:
        raise InvalidIngressEventError("cv_text must be non-empty")
    return publish_recruitment_event(
        runtime,
        candidate_id,
        "cv_submitted",
        {"cv_text": text},
        correlation_id=correlation_id,
    )


def submit_cv_pdf(
    runtime: IngressRuntime,
    candidate_id: UUID,
    pdf_base64: str,
    *,
    file_name: str = "cv.pdf",
    correlation_id: Optional[UUID] = None,
) -> EventIngressResult:
    """
    Ingest a bounded PDF CV payload and route extracted text into ``submit_cv``.

    The canonical orchestration path remains ``cv_submitted`` with plain ``cv_text``.
    """
    pdf_bytes = decode_pdf_base64(pdf_base64, file_name=file_name)
    extracted = extract_text_from_pdf_bytes(pdf_bytes, file_name=file_name)
    return submit_cv(
        runtime,
        candidate_id,
        extracted.cv_text,
        correlation_id=correlation_id,
    )


def _cv_pdf_payload_fingerprint(pdf_bytes: bytes, file_name: str) -> str:
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    return f"{digest}:{file_name.strip()}"


def _ingress_result_to_pdf_response(
    candidate_id: UUID,
    result: EventIngressResult,
) -> Dict[str, Any]:
    body: Dict[str, Any] = {
        "candidate_id": str(candidate_id),
        "ingress_accepted": result.ingress_accepted,
        "publish_status": result.publish_status,
        "event_id": result.event_id,
        "event_type": result.event_type,
        "publish_result": result.publish_result,
    }
    if result.state_summary is not None:
        body["state_summary"] = result.state_summary
    return body


def candidate_pdf_ingress_response_dict(
    candidate_id: UUID,
    result: EventIngressResult,
) -> Dict[str, Any]:
    return _ingress_result_to_pdf_response(candidate_id, result)


def create_and_submit_cv_pdf(
    runtime: IngressRuntime,
    *,
    idempotency_key: str,
    pdf_base64: str,
    file_name: str = "cv.pdf",
    correlation_id: Optional[UUID] = None,
) -> CandidatePdfIngressResult:
    """
    Single-step candidate create + CV PDF ingress (R-012).

    Order: idempotency decision (incl. ready check before write allocation) -> write.
    """
    key = str(idempotency_key or "").strip()
    if not key:
        raise IdempotencyKeyRequiredError("Idempotency-Key header is required")

    pdf_bytes = decode_pdf_base64(pdf_base64, file_name=file_name)
    fingerprint = _cv_pdf_payload_fingerprint(pdf_bytes, file_name)

    store = runtime.idempotency_store
    store.purge_expired()
    record = store.get(IDEMPOTENCY_METHOD_PATH, key)

    if record is not None and record.status == IdempotencyRecordStatus.SUCCEEDED:
        if record.payload_fingerprint != fingerprint:
            raise IdempotencyKeyConflictError(
                "idempotency_key_conflict: payload fingerprint differs from first success"
            )
        if record.response_status_code is None or record.response_body_json is None:
            raise RuntimeError("idempotency record missing stored HTTP response")
        raise IdempotencyReplayError(
            status_code=int(record.response_status_code),
            body=json.loads(record.response_body_json),
        )

    _require_ready_scoring_context(runtime)

    runtime.begin_idempotency_operation(key)
    try:
        record = store.get(IDEMPOTENCY_METHOD_PATH, key)
        if record is not None and record.status == IdempotencyRecordStatus.SUCCEEDED:
            if record.payload_fingerprint != fingerprint:
                raise IdempotencyKeyConflictError(
                    "idempotency_key_conflict: payload fingerprint differs from first success"
                )
            raise IdempotencyReplayError(
                status_code=int(record.response_status_code or 200),
                body=json.loads(record.response_body_json or "{}"),
            )

        suspected_dedup: Optional[Any] = None
        is_retry = (
            record is not None
            and record.status == IdempotencyRecordStatus.IN_PROGRESS
            and record.candidate_id
        )
        if is_retry:
            if record.payload_fingerprint != fingerprint:
                raise IdempotencyKeyConflictError(
                    "idempotency_key_conflict: payload fingerprint differs from in-flight request"
                )
            candidate_id = UUID(record.candidate_id)
        else:
            if record is not None and record.payload_fingerprint != fingerprint:
                raise IdempotencyKeyConflictError(
                    "idempotency_key_conflict: payload fingerprint differs from prior attempt"
                )
            extracted_for_dedup = extract_text_from_pdf_bytes(pdf_bytes, file_name=file_name)
            signals = extract_ingress_signals_from_cv_text(extracted_for_dedup.cv_text)
            high_eval = evaluate_dedup_high_confidence_from_ingress_signals(
                runtime.candidate_store, signals
            )
            if high_eval.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE:
                raise DuplicateCandidateHighConfidenceError(
                    "duplicate_candidate_high_confidence: email or phone matches existing candidate",
                    matches=dedup_matches_to_json(high_eval.matches),
                )
            fp_eval = evaluate_dedup_fingerprint_suspected_from_ingress_signals(
                runtime.candidate_store, signals
            )
            if fp_eval.outcome == DedupOutcome.SUSPECTED_FINGERPRINT:
                suspected_dedup = fp_eval
            candidate_id = uuid4()
            store.upsert_in_progress(
                method_path=IDEMPOTENCY_METHOD_PATH,
                idempotency_key=key,
                payload_fingerprint=fingerprint,
                candidate_id=str(candidate_id),
            )

        extracted = extract_text_from_pdf_bytes(pdf_bytes, file_name=file_name)
        ingress = submit_cv(
            runtime,
            candidate_id,
            extracted.cv_text,
            correlation_id=correlation_id,
        )
        post_eval = _evaluate_post_parse_high_confidence_dedup(runtime, candidate_id)
        if post_eval is not None and post_eval.outcome == DedupOutcome.HIGH_CONFIDENCE_DUPLICATE:
            extra = list(suspected_dedup.matches) if suspected_dedup is not None else []
            _mark_candidate_post_ingress_duplicate(
                runtime,
                candidate_id,
                post_eval,
                extra_matches=extra,
            )
        elif suspected_dedup is not None:
            _mark_candidate_suspected_duplicate(runtime, candidate_id, suspected_dedup)
        response_body = _ingress_result_to_pdf_response(candidate_id, ingress)
        dedup_payload = _dedup_extension_response_payload(runtime, candidate_id)
        if dedup_payload is not None:
            response_body["dedup"] = dedup_payload
        store.mark_succeeded(
            method_path=IDEMPOTENCY_METHOD_PATH,
            idempotency_key=key,
            response_status_code=200,
            response_body=response_body,
        )
        return CandidatePdfIngressResult(
            candidate_id=candidate_id,
            ingress_accepted=ingress.ingress_accepted,
            publish_status=ingress.publish_status,
            event_id=ingress.event_id,
            event_type=ingress.event_type,
            publish_result=ingress.publish_result,
            state_summary=ingress.state_summary,
            dedup=dedup_payload,
        )
    finally:
        runtime.end_idempotency_operation(key)


def _dedup_now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _dedup_audit_entry(
    *,
    action: str,
    actor_id: str,
    reason: str,
    target_candidate_id: Optional[UUID] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "action": action,
        "actor_id": actor_id,
        "reason": reason,
        "recorded_at": _dedup_now_utc().isoformat(),
    }
    if target_candidate_id is not None:
        entry["target_candidate_id"] = str(target_candidate_id)
    return entry


def _ingress_governance_by_candidate(
    runtime: IngressRuntime,
    *,
    now: Optional[datetime] = None,
    stale_seconds: Optional[int] = None,
) -> Dict[UUID, IngressGovernanceFlags]:
    kwargs: Dict[str, Any] = {"now": now}
    if stale_seconds is not None:
        kwargs["stale_seconds"] = stale_seconds
    return ingress_governance_by_candidate_id(
        runtime.idempotency_store.list_in_progress(),
        **kwargs,
    )


def _governance_flags_for_candidate(
    candidate: Any,
    ingress: Dict[UUID, IngressGovernanceFlags],
    candidate_id: UUID,
) -> Dict[str, Any]:
    gov = ingress.get(candidate_id)
    return governance_flags_from_candidate(
        candidate,
        ingress_in_progress=bool(gov.ingress_in_progress) if gov else False,
        orphan_ingress=bool(gov.orphan_ingress) if gov else False,
    )


def _evaluate_post_parse_high_confidence_dedup(
    runtime: IngressRuntime,
    candidate_id: UUID,
) -> Optional[DedupEvaluation]:
    got = runtime.candidate_store.get(candidate_id)
    if not got.ok or got.candidate is None:
        return None
    signals = ingress_signals_from_candidate(got.candidate)
    return evaluate_dedup_high_confidence_from_ingress_signals(
        runtime.candidate_store,
        signals,
        exclude_candidate_ids=[candidate_id],
    )


def _dedup_extension_response_payload(
    runtime: IngressRuntime,
    candidate_id: UUID,
) -> Optional[Dict[str, Any]]:
    got = runtime.candidate_store.get(candidate_id)
    if not got.ok or got.candidate is None:
        return None
    dedup = dict((got.candidate.extensions or {}).get("dedup") or {})
    if not dedup.get("status"):
        return None
    return {
        "status": dedup.get("status"),
        "pending_resolution": bool(dedup.get("pending_resolution")),
        "matches": list(dedup.get("matches") or []),
    }


def _mark_candidate_post_ingress_duplicate(
    runtime: IngressRuntime,
    candidate_id: UUID,
    dedup_eval: DedupEvaluation,
    *,
    extra_matches: Optional[Sequence[DedupMatch]] = None,
) -> None:
    got = runtime.candidate_store.get(candidate_id)
    if not got.ok or got.candidate is None or got.meta is None:
        return
    prior = dict((got.candidate.extensions or {}).get("dedup") or {})
    prior_matches = list(prior.get("matches") or [])
    groups: List[Sequence[DedupMatch | Dict[str, Any]]] = [dedup_eval.matches]
    if extra_matches:
        groups.append(extra_matches)
    if prior_matches:
        groups.append(prior_matches)
    merged = merge_dedup_matches(*groups)
    new_matches_json = dedup_matches_to_json(merged)
    if (
        prior.get("status") == "post_ingress_duplicate"
        and bool(prior.get("pending_resolution"))
        and dedup_matches_json_normalized(prior_matches)
        == dedup_matches_json_normalized(new_matches_json)
    ):
        return
    detected_at = prior.get("detected_at") or _dedup_now_utc().isoformat()
    dedup = {
        "status": "post_ingress_duplicate",
        "pending_resolution": True,
        "matches": new_matches_json,
        "detected_at": detected_at,
        "audit": list(prior.get("audit") or []),
    }
    updated = got.candidate.model_copy(
        update={"extensions": {**got.candidate.extensions, "dedup": dedup}}
    )
    runtime.candidate_store.replace(updated, expected_store_revision=got.meta.store_revision)


def _mark_candidate_suspected_duplicate(
    runtime: IngressRuntime,
    candidate_id: UUID,
    dedup_eval: Any,
) -> None:
    got = runtime.candidate_store.get(candidate_id)
    if not got.ok or got.candidate is None or got.meta is None:
        return
    dedup = {
        "status": "suspected_duplicate",
        "pending_resolution": True,
        "matches": dedup_matches_to_json(dedup_eval.matches),
        "detected_at": _dedup_now_utc().isoformat(),
        "audit": [],
    }
    updated = got.candidate.model_copy(
        update={"extensions": {**got.candidate.extensions, "dedup": dedup}}
    )
    runtime.candidate_store.replace(updated, expected_store_revision=got.meta.store_revision)


def link_candidate_dedup(
    runtime: IngressRuntime,
    source_candidate_id: UUID,
    target_candidate_id: UUID,
    *,
    actor_id: str,
    reason: str,
) -> Dict[str, Any]:
    """Record recruiter link decision (no data merge)."""
    if source_candidate_id == target_candidate_id:
        raise InvalidDedupGovernanceError("cannot link candidate to itself")
    reason_s = str(reason or "").strip()
    if not reason_s:
        raise InvalidDedupGovernanceError("reason is required")
    actor_s = str(actor_id or "").strip()
    if not actor_s:
        raise InvalidDedupGovernanceError("actor_id is required")
    got_t = runtime.candidate_store.get(target_candidate_id)
    if not got_t.ok or got_t.candidate is None:
        raise CandidateNotFoundError(f"candidate not found: {target_candidate_id!s}")
    got_s = runtime.candidate_store.get(source_candidate_id)
    if not got_s.ok or got_s.candidate is None or got_s.meta is None:
        raise CandidateNotFoundError(f"candidate not found: {source_candidate_id!s}")
    prior = dict((got_s.candidate.extensions or {}).get("dedup") or {})
    audit = list(prior.get("audit") or [])
    audit.append(
        _dedup_audit_entry(
            action="link",
            actor_id=actor_s,
            reason=reason_s,
            target_candidate_id=target_candidate_id,
        )
    )
    dedup = {
        **prior,
        "status": "linked",
        "pending_resolution": False,
        "linked_to_candidate_id": str(target_candidate_id),
        "matches": prior.get("matches") or [],
        "audit": audit,
    }
    updated = got_s.candidate.model_copy(
        update={"extensions": {**got_s.candidate.extensions, "dedup": dedup}}
    )
    runtime.candidate_store.replace(updated, expected_store_revision=got_s.meta.store_revision)
    return governance_flags_from_candidate(updated)


def get_candidate_view_for_runtime(runtime: IngressRuntime, candidate_id: UUID) -> Dict[str, Any]:
    ingress = _ingress_governance_by_candidate(runtime)
    gov = ingress.get(candidate_id)
    return _projection_candidate_view(
        runtime,
        candidate_id,
        ingress_in_progress=bool(gov.ingress_in_progress) if gov else False,
        orphan_ingress=bool(gov.orphan_ingress) if gov else False,
    )


def keep_separate_candidate_dedup(
    runtime: IngressRuntime,
    candidate_id: UUID,
    *,
    actor_id: str,
    reason: str,
) -> Dict[str, Any]:
    """Record recruiter keep-separate decision."""
    reason_s = str(reason or "").strip()
    if not reason_s:
        raise InvalidDedupGovernanceError("reason is required")
    actor_s = str(actor_id or "").strip()
    if not actor_s:
        raise InvalidDedupGovernanceError("actor_id is required")
    got = runtime.candidate_store.get(candidate_id)
    if not got.ok or got.candidate is None or got.meta is None:
        raise CandidateNotFoundError(f"candidate not found: {candidate_id!s}")
    prior = dict((got.candidate.extensions or {}).get("dedup") or {})
    audit = list(prior.get("audit") or [])
    audit.append(
        _dedup_audit_entry(action="keep_separate", actor_id=actor_s, reason=reason_s)
    )
    dedup = {
        **prior,
        "status": "keep_separate",
        "pending_resolution": False,
        "audit": audit,
    }
    updated = got.candidate.model_copy(
        update={"extensions": {**got.candidate.extensions, "dedup": dedup}}
    )
    runtime.candidate_store.replace(updated, expected_store_revision=got.meta.store_revision)
    return governance_flags_from_candidate(updated)


def clear_organization_context(runtime: IngressRuntime) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = clear_organization_from_scoring_context(current)
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def clear_recruiter_actor_context(runtime: IngressRuntime) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = clear_recruiter_actor_from_scoring_context(current)
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def clear_job_context(runtime: IngressRuntime) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    was_ready = _context_was_ready(current)
    updated = clear_job_from_scoring_context(current)
    persisted = _persist_scoring_context(runtime, updated)
    if was_ready:
        force_mark_all_candidate_evaluations_stale(runtime)
    return persisted


def record_recruiter_decision(
    runtime: IngressRuntime,
    candidate_id: UUID,
    event_type: str,
    payload: Dict[str, Any],
    *,
    correlation_id: Optional[UUID] = None,
) -> EventIngressResult:
    """Publish a governance ingress event with strict payload (no bootstrap merge)."""
    if not policies.is_governance_event(event_type):
        raise InvalidIngressEventError(
            f"event_type {event_type!r} is not governance; use publish_recruitment_event"
        )
    return publish_ingress_event(
        runtime,
        candidate_id,
        event_type,
        payload,
        correlation_id=correlation_id,
    )


def run_primary_demo_sequence(
    runtime: IngressRuntime,
    candidate_id: UUID,
) -> OrchestrationState:
    """Run the scripted primary vertical-slice sequence (requires pipeline phase NEW)."""
    _ensure_candidate_state(runtime, candidate_id)
    _ensure_demo_scoring_context_ready(runtime)
    return runtime.run_primary_demo_sequence()


def list_candidates(runtime: IngressRuntime) -> List[Dict[str, Any]]:
    """
    List lightweight summaries for every orchestration snapshot in the store.

    **Semantics (Stage B MVP):** This is a **snapshot-driven** list produced by enumerating
    persisted orchestration state ids (``store.list_all_state_ids()``) and projecting each
    latest snapshot. It is **not** a domain-level candidate registry or application catalog.

    Assumes **one candidate ↔ one orchestration state** (single application per candidate).
    Read-only: does not create state. Skips snapshots without explicit ``candidate_id``.
    """
    from .projection import load_candidate_and_snapshot_for_read

    store = runtime.bundle.store
    ingress = _ingress_governance_by_candidate(runtime)
    items: List[Dict[str, Any]] = []
    for state_id in store.list_all_state_ids():
        got = store.get(state_id)
        if not got.ok or got.snapshot is None:
            continue
        try:
            cid = got.snapshot.candidate_id
            if cid is None:
                continue
            candidate, snapshot = load_candidate_and_snapshot_for_read(runtime, cid)
            row = build_candidate_list_item(snapshot, candidate=candidate)
            row["governance_flags"] = _governance_flags_for_candidate(
                candidate, ingress, cid
            )
            items.append(row)
        except ValueError:
            continue
    def _score_sort_key(row: Dict[str, Any]) -> tuple:
        overall = row.get("overall_score") or {}
        value = overall.get("value")
        if value is None:
            return (1, 0.0, row["candidate_id"])
        try:
            return (0, -float(value), row["candidate_id"])
        except (TypeError, ValueError):
            return (1, 0.0, row["candidate_id"])

    items.sort(key=_score_sort_key)
    total = len(items)
    for idx, row in enumerate(items, start=1):
        row["rank"] = idx
        row["total_candidates"] = total
    return items


def perform_candidate_action(
    runtime: IngressRuntime,
    candidate_id: UUID,
    event_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Publish a recruiter governance ``event_type`` (existing bus path).

    Validates the candidate exists and that ``event_type`` is registry-allowed for the phase.
    """
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None:
        raise CandidateNotFoundError(f"no orchestration state for candidate: {candidate_id!s}")

    phase = got.snapshot.pipeline.phase.value
    policies.validate_recruiter_event_for_phase(
        event_type,
        phase,
        transition_extensions=dict(got.snapshot.extensions or {}),
    )
    gov_payload = dict(DEFAULT_RECRUITER_ACTION_GOVERNANCE_PAYLOAD)
    if payload:
        gov_payload.update(payload)
    try:
        gov_payload = policies.validate_recruiter_action_payload(event_type, gov_payload)
    except InvalidRecruiterActionPayloadError:
        raise

    result = record_recruiter_decision(
        runtime,
        candidate_id,
        event_type,
        gov_payload,
    )
    if not result.ingress_accepted:
        raise InvalidCandidateActionError(
            f"governance publish not accepted for {event_type!r}: {result.publish_status}"
        )
    return get_candidate_view_for_runtime(runtime, candidate_id)


# --- Canonical candidate record + orchestration dual-write ---

_logger = logging.getLogger(__name__)

SNAPSHOT_RECONCILE_MAX_ATTEMPTS = 3
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
    seen: set[UUID] = set()
    matches: List[UUID] = []
    if normalized_email:
        for cid in store.find_candidate_ids_by_normalized_email(normalized_email):
            if cid not in seen:
                seen.add(cid)
                matches.append(cid)
    if normalized_phone:
        for cid in store.find_candidate_ids_by_normalized_phone(normalized_phone):
            if cid not in seen:
                seen.add(cid)
                matches.append(cid)
    if cv_content_fingerprint:
        for cid in store.find_candidate_ids_by_cv_fingerprint(cv_content_fingerprint):
            if cid not in seen:
                seen.add(cid)
                matches.append(cid)
    return matches


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
        _logger.warning(
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
            _logger.info(
                "dual_write snapshot_replace_ok candidate_id=%s state_id=%s attempt=%s",
                candidate_id,
                state_id,
                attempt,
            )
            return PersistDualWriteOutcome(
                ok=True,
                candidate_revision=cand.evaluation_revision,
            )
        _logger.warning(
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

    _logger.warning(
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
