"""
Recruitment application use cases (ingress publish, demo sequence).

Runtime is always passed in by the API layer; this module does not construct runtimes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Protocol
from uuid import UUID

from interfaces.event_bus_interface import DeliveryStatus
from runtime.in_memory_state_store import StateStoreFailureCode
from .state_init import initial_orchestration_state
from .ingress import FIXED_CLOCK as _FIXED_CLOCK
from .ingress import build_ingress_envelope as _envelope
from schemas.state_schema import OrchestrationState

from . import policies
from .exceptions import DemoRunPreconditionError, InvalidIngressEventError
from .projection import get_state_summary
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
