"""
Application-level recruitment policies (ingress allowlist, governance, single-tenant).

Does not encode transition graph legality or planner routing — those remain in
``state_machine`` / ``orchestrator`` respectively.

This module is the **single source** for allowed API ingress event type names.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol, Tuple
from uuid import UUID

from schemas.governance_schema import GOVERNANCE_EVENT_TYPES

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

# API / integration allowlist = primary progression + governance + bounded system ingress.
VERTICAL_SLICE_INGRESS_EVENT_TYPES: Tuple[str, ...] = (
    PRIMARY_VERTICAL_SLICE_EVENT_TYPES + GOVERNANCE_EVENT_TYPES + ("candidate_rejected",)
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
