"""
Recruitment application use cases (ingress publish, demo sequence).

Runtime is always passed in by the API layer; this module does not construct runtimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol
from uuid import UUID

from interfaces.event_bus_interface import DeliveryStatus
from runtime.in_memory_state_store import StateStoreFailureCode
from .state_init import initial_orchestration_state
from .ingress import FIXED_CLOCK as _FIXED_CLOCK
from .ingress import build_ingress_envelope as _envelope
from schemas.state_schema import OrchestrationState

from . import policies
from .exceptions import (
    CandidateNotFoundError,
    DemoRunPreconditionError,
    InvalidCandidateActionError,
    InvalidIngressEventError,
    InvalidScoringContextError,
    ScoringContextNotReadyError,
    ScoringFailedError,
)
from .pdf_ingest import decode_pdf_base64, extract_text_from_pdf_bytes
from .projection import build_candidate_list_item, get_candidate_view_for_runtime, get_state_summary
from .scoring_context_service import (
    mark_evaluation_stale,
    normalize_job_context_from_answers,
    normalize_job_context_from_text,
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
    def scoring_context_store(self) -> Any: ...

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


def _mark_existing_candidate_evaluations_stale(
    runtime: IngressRuntime, *, active_context_version: int
) -> None:
    store = runtime.bundle.store
    for state_id in store.list_all_state_ids():
        got = store.get(state_id)
        if not got.ok or got.snapshot is None or got.meta is None:
            continue
        snapshot = got.snapshot
        evaluation = snapshot.evaluation
        if evaluation is None:
            continue
        changed = False
        next_light = mark_evaluation_stale(
            evaluation.light, active_context_version=active_context_version
        )
        next_deep = mark_evaluation_stale(
            evaluation.deep, active_context_version=active_context_version
        )
        if next_light is not evaluation.light or next_deep is not evaluation.deep:
            changed = True
        if not changed:
            continue
        next_evaluation = _model_copy_local(
            evaluation,
            light=next_light,
            deep=next_deep,
        )
        next_snapshot = _model_copy_local(snapshot, evaluation=next_evaluation)
        store.replace(
            state_id,
            next_snapshot,
            expected_store_revision=got.meta.store_revision,
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
    updated = update_scoring_context(current, organization_context=context, source_refs=context.source_refs)
    persisted = _persist_scoring_context(runtime, updated)
    _mark_existing_candidate_evaluations_stale(
        runtime, active_context_version=persisted.context_version
    )
    return persisted


def author_recruiter_actor_context(
    runtime: IngressRuntime,
    context: RecruiterActorContext,
) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    updated = update_scoring_context(
        current,
        recruiter_actor_context=context,
        source_refs=context.source_refs,
    )
    persisted = _persist_scoring_context(runtime, updated)
    _mark_existing_candidate_evaluations_stale(
        runtime, active_context_version=persisted.context_version
    )
    return persisted


def author_job_context(
    runtime: IngressRuntime,
    context: JobContext,
) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    updated = update_scoring_context(current, job_context=context, source_refs=context.source_refs)
    persisted = _persist_scoring_context(runtime, updated)
    _mark_existing_candidate_evaluations_stale(
        runtime, active_context_version=persisted.context_version
    )
    return persisted


def author_job_context_from_text(
    runtime: IngressRuntime,
    raw_text: str,
    *,
    source_ref: Optional[str] = None,
) -> ScoringContext:
    try:
        job = normalize_job_context_from_text(
            raw_text,
            source_refs=[source_ref] if source_ref else None,
        )
    except ValueError as exc:
        raise InvalidScoringContextError(str(exc)) from exc
    return author_job_context(runtime, job)


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
    try:
        job = normalize_job_context_from_answers(
            role_title=role_title,
            must_haves_answer=must_haves_answer,
            preferred_answer=preferred_answer,
            success_answer=success_answer,
            responsibilities_answer=responsibilities_answer,
            source_refs=["normalized://recruiter_answers/job_context"],
        )
    except ValueError as exc:
        raise InvalidScoringContextError(str(exc)) from exc
    return author_job_context(runtime, job)


def refresh_active_scoring_context(runtime: IngressRuntime) -> ScoringContext:
    current = get_active_scoring_context(runtime)
    refreshed = refresh_scoring_context(current)
    if refreshed.status != ScoringContextStatus.READY:
        raise InvalidScoringContextError(
            "scoring_context cannot become ready until organization_context, "
            "recruiter_actor_context, and job_context contain sufficient signals and "
            "deterministic L2/L3 criteria derivation succeeds"
        )
    return _persist_scoring_context(runtime, refreshed)


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
    Read-only: does not create state. Skips rows without a candidate ``StateLink``.
    """
    store = runtime.bundle.store
    items: List[Dict[str, Any]] = []
    for state_id in store.list_all_state_ids():
        got = store.get(state_id)
        if not got.ok or got.snapshot is None:
            continue
        try:
            items.append(build_candidate_list_item(got.snapshot))
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

    TODO: Different recruiter actions will need structured payloads (e.g. interview slot,
    offer terms). ``payload`` is untyped ``Dict[str, Any]`` merged over API defaults today.
    """
    got = runtime.bundle.store.get_for_candidate(candidate_id)
    if not got.ok or got.snapshot is None:
        raise CandidateNotFoundError(f"no orchestration state for candidate: {candidate_id!s}")

    phase = got.snapshot.pipeline.phase.value
    policies.validate_recruiter_event_for_phase(event_type, phase)
    gov_payload = dict(DEFAULT_RECRUITER_ACTION_GOVERNANCE_PAYLOAD)
    if payload:
        gov_payload.update(payload)

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
