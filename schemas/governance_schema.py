"""
Deterministic governance payload contracts for human operator ingress events.

Validation-only: no routing or orchestration logic. Planners map validated payloads
into :class:`~orchestrator.orchestrator.ProposedTransition` records that still pass
through the transition engine.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

try:
    from pydantic import ConfigDict

    _V2 = True
except Exception:  # pragma: no cover
    _V2 = False


class GovernanceActorType(str, Enum):
    """Stable actor classification for audit (not RBAC)."""

    RECRUITER = "recruiter"
    OPERATOR = "operator"
    HUMAN_OTHER = "human_other"


class GovernanceIngressPayload(BaseModel):
    """
    Required governance fields for recruiter/operator-driven ingress events.

    Carried in :class:`~interfaces.event_bus_interface.EventEnvelope` ``payload``.
    """

    if _V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
            frozen=True,
        )

    actor_id: str = Field(..., min_length=1, description="Stable actor identifier for audit.")
    actor_type: GovernanceActorType
    reason: str = Field(..., min_length=1, description="Human-entered justification.")
    evidence_refs: Tuple[str, ...] = Field(
        default_factory=tuple,
        description="Optional artifact/evidence references (keys/URIs).",
    )
    override_rationale: Optional[str] = Field(
        default=None,
        description="Optional free-text override narrative (audit; not routing input).",
    )
    lineage_parent_event_id: Optional[UUID] = Field(
        default=None,
        description="Optional prior event this governance action responds to.",
    )


class GovernanceOverrideIngressPayload(GovernanceIngressPayload):
    """
    Bounded explicit transition request (still validated by the transition engine).

    ``requested_*`` must match the current pipeline snapshot when the planner applies
    the transition; mismatch yields orchestrator state mismatch (no bypass).
    """

    requested_from_phase: str = Field(..., min_length=1)
    requested_to_phase: str = Field(..., min_length=1)
    trigger: str = Field(
        ...,
        min_length=1,
        description="Trigger passed to TransitionContext (event:*, manual_*, or system_*).",
    )
    force_human_override: bool = Field(
        default=False,
        description="When true, ProposedTransition.human_override is set (terminal escape only).",
    )


GOVERNANCE_EVENT_TYPES: Tuple[str, ...] = (
    "recruiter_approve_candidate",
    "recruiter_reject_candidate",
    "recruiter_schedule_interview",
    "recruiter_complete_interview",
    "recruiter_send_offer",
    "recruiter_mark_hired",
    "recruiter_override_transition",
    "recruiter_force_transition",
)


def parse_governance_ingress(payload: Dict[str, Any]) -> GovernanceIngressPayload:
    return GovernanceIngressPayload.model_validate(payload)


def parse_governance_override_ingress(payload: Dict[str, Any]) -> GovernanceOverrideIngressPayload:
    return GovernanceOverrideIngressPayload.model_validate(payload)


def governance_record_extensions(
    *,
    event_type: str,
    gov: GovernanceIngressPayload,
    decision_code: str,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Deterministic transition-record extensions for inspection/replay (strings only where possible)."""
    base: Dict[str, Any] = {
        "governance.event_type": event_type,
        "governance.decision_code": decision_code,
        "governance.actor_id": gov.actor_id,
        "governance.actor_type": gov.actor_type.value,
        "governance.reason": gov.reason,
        "governance.evidence_refs": list(gov.evidence_refs),
    }
    if gov.override_rationale:
        base["governance.override_rationale"] = gov.override_rationale
    if gov.lineage_parent_event_id is not None:
        base["governance.lineage_parent_event_id"] = str(gov.lineage_parent_event_id)
    if extra:
        base.update(extra)
    return base
