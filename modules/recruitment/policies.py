"""
Application-level recruitment policies (ingress allowlist, governance, single-tenant).

Recruiter **actions** are a projection of ``default_pipeline_registry()`` rules only
(no duplicate action-key or trigger mapping tables).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypedDict
from uuid import UUID

from schemas.governance_schema import GOVERNANCE_EVENT_TYPES
from schemas.state_schema import PipelinePhase, StateDomain
from state_machine.transition_engine import (
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

# Public HTTP allowlist excludes ``candidate_created``; write-path use cases may still
# publish it directly for demo/runtime tests.
PUBLIC_VERTICAL_SLICE_EVENT_TYPES: Tuple[str, ...] = tuple(
    et for et in PRIMARY_VERTICAL_SLICE_EVENT_TYPES if et != "candidate_created"
)

PUBLIC_API_INGRESS_EVENT_TYPES: Tuple[str, ...] = (
    PUBLIC_VERTICAL_SLICE_EVENT_TYPES
    + ("cv_submitted",)
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


# UI labels keyed by ``event_type`` — not a phase→action map; registry drives availability.
ACTION_DESCRIPTORS: Dict[str, ActionDescriptor] = {
    "recruiter_schedule_interview": {
        "event_type": "recruiter_schedule_interview",
        "label": "Schedule Interview",
    },
    "recruiter_complete_interview": {
        "event_type": "recruiter_complete_interview",
        "label": "Complete Interview",
    },
    "recruiter_send_offer": {
        "event_type": "recruiter_send_offer",
        "label": "Send Offer",
    },
    "recruiter_reject_candidate": {
        "event_type": "recruiter_reject_candidate",
        "label": "Reject Candidate",
    },
    "recruiter_reconsider_candidate": {
        "event_type": "recruiter_reconsider_candidate",
        "label": "Reconsider Candidate",
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


def _recruiter_actions_from_rule(rule: TransitionRule) -> List[RecruiterAction]:
    """Build recruiter actions for one registry edge (manual recruiter triggers only)."""
    inactive = PipelinePhase.INACTIVE.value
    out: List[RecruiterAction] = []
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
                "key": event_type,
                "label": label_for_recruiter_action(event_type),
                "event_type": event_type,
            }
        )
    return out


def get_available_actions_for_phase(
    phase: str,
    *,
    registry: Optional[TransitionRegistry] = None,
) -> List[RecruiterAction]:
    """
    Derive recruiter actions solely from transition registry rules for ``phase``.

    An action appears iff a rule applies (``from_state`` is ``phase`` or ``*``) and carries a
    ``manual_recruiter_*`` trigger that resolves to a recruiter governance ``event_type``.
    """
    seen: set[str] = set()
    actions: List[RecruiterAction] = []
    for rule in get_allowed_transitions_for_phase(phase, registry=registry):
        for action in _recruiter_actions_from_rule(rule):
            et = action["event_type"]
            if et in seen:
                continue
            seen.add(et)
            actions.append(action)
    actions.sort(key=lambda a: a["event_type"])
    return actions


def validate_recruiter_event_for_phase(event_type: str, phase: str) -> None:
    """
    Ensure ``event_type`` is an allowed recruiter action for ``phase`` (registry-derived).

    Raises:
        InvalidCandidateActionError: when not allowed for ``phase``.
    """
    from .exceptions import InvalidCandidateActionError

    if not is_recruiter_governance_event(event_type):
        raise InvalidCandidateActionError(f"not a recruiter governance event: {event_type!r}")

    allowed = {a["event_type"] for a in get_available_actions_for_phase(phase)}
    if event_type not in allowed:
        raise InvalidCandidateActionError(
            f"event_type {event_type!r} is not valid for pipeline phase {phase!r}"
        )


def resolve_event_type_for_action(event_type: str, phase: str) -> str:
    """Validate ``event_type`` for ``phase``; returns ``event_type`` when allowed."""
    validate_recruiter_event_for_phase(event_type, phase)
    return event_type
