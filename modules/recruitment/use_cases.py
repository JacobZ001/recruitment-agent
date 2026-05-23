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
)
from .projection import build_candidate_list_item, get_candidate_view_for_runtime, get_state_summary

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
    env = env.model_copy(update={"payload": merged_payload})

    pr = runtime.bundle.bus.publish(env)
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
    event_type: str,
    payload: Dict[str, Any],
    *,
    correlation_id: Optional[UUID] = None,
) -> EventIngressResult:
    """Deprecated alias for :func:`publish_recruitment_event` (name retained for compatibility)."""
    return publish_recruitment_event(
        runtime,
        candidate_id,
        event_type,
        payload,
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
    # TODO: recruiter-facing sort (recency / stage / score)
    # current sort is deterministic only, not product semantics
    items.sort(key=lambda row: row["candidate_id"])
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
