"""
Application-level recruitment policies (ingress allowlist, governance, single-tenant).

Recruiter **actions** are a projection of ``default_pipeline_registry()`` rules only
(no duplicate action-key or trigger mapping tables).
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Protocol, Tuple, TypedDict, Type
from uuid import UUID

from pydantic import BaseModel, ValidationError

from schemas.governance_schema import GOVERNANCE_EVENT_TYPES
from schemas.governance_schema import GovernanceIngressPayload
from schemas.state_schema import DecisionActorType, PipelinePhase, StateActor, StateDomain
from state_machine.transition_engine import (
    GuardEvaluation,
    TransitionContext,
    TransitionEngine,
    TransitionGuard,
    TransitionRegistry,
    TransitionRule,
    default_pipeline_registry,
)

# Canonical scripted primary progression (deterministic planner/registry sequence).
PRIMARY_VERTICAL_SLICE_EVENT_TYPES: Tuple[str, ...] = (
    "candidate_created",
    "cv_uploaded",
    "cv_parsed",
    "hard_filter_passed",
    "light_scoring_completed",
    "questionnaire_sent",
    "questionnaire_completed",
    "deep_scoring_completed",
)

PUBLIC_API_INGRESS_EVENT_TYPES: Tuple[str, ...] = (
    ("cv_submitted",)
    + GOVERNANCE_EVENT_TYPES
    + ("candidate_rejected",)
)

VERTICAL_SLICE_INGRESS_EVENT_TYPES: Tuple[str, ...] = (
    PRIMARY_VERTICAL_SLICE_EVENT_TYPES
    + ("cv_submitted",)
    + GOVERNANCE_EVENT_TYPES
    + ("candidate_rejected",)
)

ALLOWED_INGRESS_EVENT_TYPES: Tuple[str, ...] = VERTICAL_SLICE_INGRESS_EVENT_TYPES

_ALLOWED_INGRESS = frozenset(ALLOWED_INGRESS_EVENT_TYPES)
_GOVERNANCE = frozenset(GOVERNANCE_EVENT_TYPES)


def allowed_ingress_event_types() -> Tuple[str, ...]:
    """Return the allowed vertical-slice ingress event type names (immutable tuple)."""
    return ALLOWED_INGRESS_EVENT_TYPES


class SingleTenantRuntime(Protocol):
    """Minimal runtime surface required for policy checks (no API types)."""

    @property
    def candidate_id(self) -> UUID: ...


def is_allowed_ingress_event(event_type: str) -> bool:
    return event_type in _ALLOWED_INGRESS


def is_governance_event(event_type: str) -> bool:
    return event_type in _GOVERNANCE


def is_recruiter_governance_event(event_type: str) -> bool:
    """True when ``event_type`` is a recruiter-driven governance ingress (not candidate/system)."""
    return event_type.startswith("recruiter_") and event_type in _GOVERNANCE


class ActionDescriptor(TypedDict):
    """UI metadata for a recruiter governance ``event_type`` (availability still from registry)."""

    event_type: str
    label: str
    group: str
    order: int


# UI labels keyed by ``event_type`` — not a phase→action map; registry drives availability.
ACTION_DESCRIPTORS: Dict[str, ActionDescriptor] = {
    "recruiter_schedule_interview": {
        "event_type": "recruiter_schedule_interview",
        "label": "Schedule Interview",
        "group": "interview",
        "order": 30,
    },
    "recruiter_complete_interview": {
        "event_type": "recruiter_complete_interview",
        "label": "Complete Interview",
        "group": "interview",
        "order": 40,
    },
    "recruiter_send_offer": {
        "event_type": "recruiter_send_offer",
        "label": "Send Offer",
        "group": "offer",
        "order": 50,
    },
    "recruiter_reject_candidate": {
        "event_type": "recruiter_reject_candidate",
        "label": "Reject Candidate",
        "group": "decision",
        "order": 90,
    },
    "recruiter_reconsider_candidate": {
        "event_type": "recruiter_reconsider_candidate",
        "label": "Reconsider Candidate",
        "group": "recovery",
        "order": 10,
    },
}


def label_from_event_type(event_type: str) -> str:
    """
    Fallback human-readable label from governance ``event_type`` (string transform).

    Strips ``recruiter_``, replaces underscores with spaces, title-cases words.
    """
    tail = event_type.removeprefix("recruiter_")
    return " ".join(word.capitalize() for word in tail.split("_") if word)


def label_for_recruiter_action(event_type: str) -> str:
    """Resolve UI label from ``ACTION_DESCRIPTORS`` or ``label_from_event_type`` fallback."""
    descriptor = ACTION_DESCRIPTORS.get(event_type)
    if descriptor is not None:
        return descriptor["label"]
    # missing descriptor: registry may expose events before catalog is updated
    return label_from_event_type(event_type)


def _group_for_recruiter_action(event_type: str) -> str:
    descriptor = ACTION_DESCRIPTORS.get(event_type)
    if descriptor is not None:
        return descriptor["group"]
    if "reconsider" in event_type:
        return "recovery"
    if "shortlist" in event_type or "approve" in event_type or "reject" in event_type:
        return "decision"
    if "interview" in event_type:
        return "interview"
    if "offer" in event_type or "hired" in event_type:
        return "offer"
    return "decision"


def _order_for_recruiter_action(event_type: str) -> int:
    descriptor = ACTION_DESCRIPTORS.get(event_type)
    if descriptor is not None:
        return int(descriptor["order"])
    if "reconsider" in event_type:
        return 10
    if "shortlist" in event_type or "approve" in event_type:
        return 20
    if "interview" in event_type and "schedule" in event_type:
        return 30
    if "interview" in event_type and "complete" in event_type:
        return 40
    if "send_offer" in event_type:
        return 50
    if "mark_hired" in event_type:
        return 60
    if "reject" in event_type:
        return 90
    return 999


def _action_item(event_type: str) -> RecruiterAction:
    return {
        "key": event_type,
        "label": label_for_recruiter_action(event_type),
        "event_type": event_type,
        "group": _group_for_recruiter_action(event_type),
        "order": _order_for_recruiter_action(event_type),
    }


def event_type_from_manual_trigger(trigger: str) -> Optional[str]:
    """
    Resolve governance ``event_type`` from a registry ``manual_recruiter_*`` trigger.

    Uses the canonical governance vocabulary only (no parallel mapping dict).
    """
    if not trigger.startswith("manual_recruiter_"):
        return None
    base = f"recruiter_{trigger.removeprefix('manual_recruiter_')}"
    if is_recruiter_governance_event(base):
        return base
    suffixed = f"{base}_candidate"
    if is_recruiter_governance_event(suffixed):
        return suffixed
    return None


def validate_single_tenant_candidate(runtime: SingleTenantRuntime, candidate_id: UUID) -> None:
    """
    Ensure ``candidate_id`` matches the wired single-aggregate runtime.

    Raises:
        CandidateNotFoundError: when the id does not match the runtime candidate.
    """
    from .exceptions import CandidateNotFoundError

    if candidate_id != runtime.candidate_id:
        raise CandidateNotFoundError(
            f"candidate_id does not match this single-aggregate runtime: {candidate_id!s}"
        )


def merge_non_governance_publish_payload(
    base_payload: Dict[str, Any],
    extra: Dict[str, Any],
    *,
    seq: int,
) -> Dict[str, Any]:
    """Merge client payload with bootstrap envelope fields for non-governance ingress."""
    out = dict(base_payload)
    out.update(extra)
    out["api_sequence"] = seq
    return out


class RecruiterAction(TypedDict):
    """Recruiter-facing action descriptor; ``key`` and ``event_type`` are the same string."""

    key: str
    label: str
    event_type: str
    group: str
    order: int


class _RecruiterActionCandidate(TypedDict):
    event_type: str
    trigger: str
    to_state: str
    rule_id: str


class _RecruiterActionBasePayload(GovernanceIngressPayload):
    pass


_RECRUITER_ACTION_PAYLOAD_MODELS: Dict[str, Type[BaseModel]] = {
    "recruiter_shortlist_candidate": _RecruiterActionBasePayload,
    "recruiter_reject_candidate": _RecruiterActionBasePayload,
    "recruiter_schedule_interview": _RecruiterActionBasePayload,
    "recruiter_complete_interview": _RecruiterActionBasePayload,
    "recruiter_send_offer": _RecruiterActionBasePayload,
    "recruiter_reconsider_candidate": _RecruiterActionBasePayload,
    "recruiter_approve_candidate": _RecruiterActionBasePayload,
    "recruiter_mark_hired": _RecruiterActionBasePayload,
}


def get_allowed_transitions_for_phase(
    phase: str,
    *,
    registry: Optional[TransitionRegistry] = None,
) -> List[TransitionRule]:
    """
    Return pipeline transition rules applicable from ``phase`` (includes ``from_state="*"``).

    Uses ``default_pipeline_registry()``; does not mutate the engine.
    """
    reg = registry if registry is not None else default_pipeline_registry()
    terminals = reg.terminal_states.get(StateDomain.PIPELINE, frozenset())
    if phase in terminals:
        return []
    out: List[TransitionRule] = []
    for rule in reg.rules:
        if rule.state_domain != StateDomain.PIPELINE:
            continue
        if rule.from_state != phase and rule.from_state != "*":
            continue
        out.append(rule)
    return out


def _recruiter_action_candidates_from_rule(rule: TransitionRule) -> List[_RecruiterActionCandidate]:
    """Build recruiter action candidates for one registry edge (manual recruiter triggers only)."""
    inactive = PipelinePhase.INACTIVE.value
    out: List[_RecruiterActionCandidate] = []
    for trigger in rule.allowed_triggers:
        if not trigger.startswith("manual_recruiter_"):
            continue
        event_type = event_type_from_manual_trigger(trigger)
        if event_type is None:
            continue
        if event_type == "recruiter_reject_candidate" and rule.to_state != inactive:
            continue
        out.append(
            {
                "event_type": event_type,
                "trigger": trigger,
                "to_state": rule.to_state,
                "rule_id": rule.rule_id,
            }
        )
    return out


def get_available_actions_for_phase(
    phase: str,
    *,
    registry: Optional[TransitionRegistry] = None,
    guards: Optional[Mapping[str, TransitionGuard]] = None,
    transition_extensions: Optional[Dict[str, Any]] = None,
) -> List[RecruiterAction]:
    """
    Derive recruiter actions solely from transition registry rules for ``phase``.

    An action appears iff a rule applies (``from_state`` is ``phase`` or ``*``) and carries a
    ``manual_recruiter_*`` trigger that resolves to a recruiter governance ``event_type``.
    """
    reg = registry if registry is not None else default_pipeline_registry()
    engine = TransitionEngine(reg, guards=guards)
    seen: set[str] = set()
    actions: List[RecruiterAction] = []
    for rule in get_allowed_transitions_for_phase(phase, registry=reg):
        for candidate in _recruiter_action_candidates_from_rule(rule):
            et = candidate["event_type"]
            if et in seen:
                continue
            ctx = TransitionContext(
                state_domain=StateDomain.PIPELINE,
                from_state=phase,
                to_state=candidate["to_state"],
                trigger=candidate["trigger"],
                actor=StateActor(
                    actor_type=DecisionActorType.HUMAN,
                    actor_id="recruiter_surface_projection",
                ),
                extensions=dict(transition_extensions or {}),
            )
            validation = engine.validate(ctx)
            if not validation.ok:
                continue
            seen.add(et)
            actions.append(_action_item(et))
    actions.sort(key=lambda a: (int(a["order"]), a["label"], a["event_type"]))
    return actions


def validate_recruiter_event_for_phase(
    event_type: str,
    phase: str,
    *,
    registry: Optional[TransitionRegistry] = None,
    guards: Optional[Mapping[str, TransitionGuard]] = None,
    transition_extensions: Optional[Dict[str, Any]] = None,
) -> RecruiterAction:
    """
    Ensure ``event_type`` is an allowed recruiter action for ``phase`` (registry-derived).

    Raises:
        InvalidCandidateActionError: when not allowed for ``phase``.
    """
    from .exceptions import InvalidCandidateActionError

    if not is_recruiter_governance_event(event_type):
        raise InvalidCandidateActionError(f"not a recruiter governance event: {event_type!r}")
    reg = registry if registry is not None else default_pipeline_registry()
    engine = TransitionEngine(reg, guards=guards)
    candidates: List[_RecruiterActionCandidate] = []
    for rule in get_allowed_transitions_for_phase(phase, registry=reg):
        for candidate in _recruiter_action_candidates_from_rule(rule):
            if candidate["event_type"] == event_type:
                candidates.append(candidate)
    if not candidates:
        raise InvalidCandidateActionError(
            f"event_type {event_type!r} is not valid for pipeline phase {phase!r}"
        )
    first_guard_message: Optional[str] = None
    for candidate in candidates:
        ctx = TransitionContext(
            state_domain=StateDomain.PIPELINE,
            from_state=phase,
            to_state=candidate["to_state"],
            trigger=candidate["trigger"],
            actor=StateActor(
                actor_type=DecisionActorType.HUMAN,
                actor_id="recruiter_action_validation",
            ),
            extensions=dict(transition_extensions or {}),
        )
        validation = engine.validate(ctx)
        if validation.ok:
            return _action_item(event_type)
        if validation.rejections:
            first_guard_message = validation.rejections[0].message
    if first_guard_message:
        raise InvalidCandidateActionError(
            f"event_type {event_type!r} is currently unavailable for pipeline phase {phase!r}: "
            f"{first_guard_message}"
        )
    raise InvalidCandidateActionError(
        f"event_type {event_type!r} is not valid for pipeline phase {phase!r}"
    )


def resolve_event_type_for_action(event_type: str, phase: str) -> str:
    """Validate ``event_type`` for ``phase``; returns ``event_type`` when allowed."""
    validate_recruiter_event_for_phase(event_type, phase)
    return event_type


def validate_recruiter_action_payload(event_type: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate recruiter action payload using a deterministic per-event model registry."""
    from .exceptions import InvalidRecruiterActionPayloadError

    model = _RECRUITER_ACTION_PAYLOAD_MODELS.get(event_type)
    if model is None:
        raise InvalidRecruiterActionPayloadError(
            f"no recruiter action payload validator registered for {event_type!r}"
        )
    try:
        if hasattr(model, "model_validate"):
            parsed = model.model_validate(payload)
            return parsed.model_dump(mode="json")
        parsed = model.parse_obj(payload)
        return parsed.dict()
    except ValidationError as exc:
        raise InvalidRecruiterActionPayloadError(
            f"invalid payload for recruiter action {event_type!r}: {exc}"
        ) from exc
