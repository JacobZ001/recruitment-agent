from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, field_validator

    _PYDANTIC_V2 = True
except Exception:  # Pydantic v1 fallback
    from pydantic import validator as field_validator  # type: ignore

    _PYDANTIC_V2 = False


class _SchemaBase(BaseModel):
    """
    Shared schema base.

    Notes:
    - This is intentionally validation-focused only (no orchestration / routing logic).
    - Forward compatibility is achieved via explicit `extensions` fields.
    """

    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
        )
    else:

        class Config:  # pragma: no cover (runtime-selected by Pydantic major version)
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True


class StateSchemaVersion(str, Enum):
    V1 = "1.0"


class PipelinePhase(str, Enum):
    NEW = "new"
    CV_RECEIVED = "cv_received"
    CV_PARSED = "cv_parsed"
    HARD_FILTER_PASSED = "hard_filter_passed"
    LIGHT_SCORED = "light_scored"
    QUESTIONNAIRE_PENDING = "questionnaire_pending"
    QUESTIONNAIRE_SENT = "questionnaire_sent"
    QUESTIONNAIRE_COMPLETED = "questionnaire_completed"
    DEEP_SCORED = "deep_scored"
    SHORTLISTED = "shortlisted"
    INTERVIEW_PENDING = "interview_pending"
    INTERVIEW_COMPLETED = "interview_completed"
    OFFER_SENT = "offer_sent"
    HIRED = "hired"
    INACTIVE = "inactive"


class PipelineStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class DecisionOutcome(str, Enum):
    UNDECIDED = "undecided"
    ADVANCE = "advance"
    HOLD = "hold"
    REJECT = "reject"
    APPROVED = "approved"
    SHORTLISTED = "shortlisted"
    OVERRIDDEN = "overridden"


class DecisionActorType(str, Enum):
    HUMAN = "human"
    SYSTEM = "system"
    LLM_SIGNAL = "llm_signal"


class StateDomain(str, Enum):
    PIPELINE = "pipeline"
    DECISION = "decision"
    COMMUNICATION = "communication"


class StateActor(_SchemaBase):
    """
    Minimal actor reference for auditing transitions and decisions.
    """

    actor_type: DecisionActorType
    actor_id: Optional[str] = Field(
        default=None, description="Optional identifier of the actor (human/system)."
    )


class StateTransitionRecord(_SchemaBase):
    state_domain: StateDomain = Field(default=StateDomain.PIPELINE)
    from_state: str = Field(..., min_length=1)
    to_state: str = Field(..., min_length=1)
    trigger: str = Field(
        ...,
        min_length=1,
        description="External trigger/event name (not routing logic).",
        examples=["event:cv_parsed", "manual_override", "integration:telegram_reply"],
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: StateActor
    event_id: Optional[UUID] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("from_state", "to_state")
    def _transition_state_matches_domain(cls, v, values=None, **_kwargs):  # type: ignore[override]
        domain = None
        try:
            domain = getattr(values, "data", None) and values.data.get("state_domain")  # type: ignore[attr-defined]
        except Exception:
            pass
        if domain is None and isinstance(values, dict):
            domain = values.get("state_domain")

        if domain == StateDomain.PIPELINE:
            allowed = {e.value for e in PipelinePhase}
        elif domain == StateDomain.DECISION:
            allowed = {e.value for e in DecisionOutcome}
        elif domain == StateDomain.COMMUNICATION:
            allowed = {e.value for e in CommunicationStatus}
        else:
            allowed = None

        if allowed is not None and v not in allowed:
            raise ValueError(f"Invalid state '{v}' for state_domain='{domain.value}'")
        return v


class CommunicationChannel(str, Enum):
    EMAIL = "email"
    TELEGRAM = "telegram"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    IN_PERSON = "in_person"
    OTHER = "other"


class CommunicationStatus(str, Enum):
    NOT_CONTACTED = "not_contacted"
    OUTREACH_PENDING = "outreach_pending"
    OUTREACH_SENT = "outreach_sent"
    AWAITING_REPLY = "awaiting_reply"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    DO_NOT_CONTACT = "do_not_contact"


class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class StateAudit(_SchemaBase):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = Field(
        default=None,
        description="Identifier for the component/operator that performed the last update.",
        examples=["orchestrator", "human_operator:jane.doe", "integration:telegram"],
    )


class StateLink(_SchemaBase):
    """
    Generic linkage to other entities/schemas without importing them here.
    """

    kind: str = Field(..., min_length=1, examples=["candidate", "job", "event"])
    id: UUID
    source: Optional[str] = Field(default=None, description="Origin system namespace.")


class PipelineState(_SchemaBase):
    """
    Where the candidate is in the deterministic pipeline lifecycle.
    """

    phase: PipelinePhase = Field(default=PipelinePhase.NEW)
    status: PipelineStatus = Field(default=PipelineStatus.ACTIVE)
    entered_phase_at: datetime = Field(default_factory=datetime.utcnow)

    last_event_id: Optional[UUID] = Field(
        default=None, description="Most recent event applied to this state."
    )
    last_transition_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the most recent phase/status change."
    )

    blocking_reasons: List[str] = Field(
        default_factory=list,
        description="Validation-friendly reasons the pipeline is blocked/paused.",
    )
    tags: List[str] = Field(default_factory=list, description="Lightweight labels.")

    extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Forward-compatible expansion point for pipeline-specific fields.",
    )


class DecisionRecommendation(_SchemaBase):
    """
    Non-binding signal produced by a component (including LLM skills).
    """

    source: str = Field(..., min_length=1, examples=["skills.llm.initial_scoring"])
    recommended_outcome: DecisionOutcome
    confidence: Optional[float] = Field(
        default=None, ge=0.0, le=1.0, description="Confidence in [0, 1]."
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="References/keys to stored evidence (not raw content).",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class DecisionRecord(_SchemaBase):
    """
    A decision action taken by a human or deterministic system component.
    """

    actor_type: DecisionActorType
    actor_id: Optional[str] = Field(
        default=None, description="Optional identifier of the actor (human/system)."
    )
    outcome: DecisionOutcome
    reason: Optional[str] = Field(
        default=None, description="Short rationale (no scoring/ranking logic)."
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="References/keys to structured evidence (not raw content).",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    event_id: Optional[UUID] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class DecisionState(_SchemaBase):
    """
    Tracks recommendations, human overrides, and the current validated outcome.
    """

    current_outcome: DecisionOutcome = Field(default=DecisionOutcome.UNDECIDED)
    finalized_at: Optional[datetime] = Field(
        default=None, description="When the outcome became final (if applicable)."
    )

    recommendations: List[DecisionRecommendation] = Field(default_factory=list)
    history: List[DecisionRecord] = Field(default_factory=list)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class MessageRecord(_SchemaBase):
    channel: CommunicationChannel
    direction: MessageDirection

    sent_at: datetime = Field(default_factory=datetime.utcnow)
    provider_message_id: Optional[str] = Field(default=None)

    template_id: Optional[str] = Field(
        default=None, description="Template identifier, if applicable."
    )
    content_ref: Optional[str] = Field(
        default=None,
        description="Reference key to stored message content (avoid duplicating text).",
    )

    status: Optional[str] = Field(
        default=None,
        description="Provider-specific status string (delivery/read/etc.).",
    )
    error: Optional[str] = Field(default=None, description="Delivery error, if any.")

    extensions: Dict[str, Any] = Field(default_factory=dict)


class CommunicationState(_SchemaBase):
    """
    Tracks outreach + conversation lifecycle without embedding messaging logic.
    """

    status: CommunicationStatus = Field(default=CommunicationStatus.NOT_CONTACTED)
    preferred_channel: Optional[CommunicationChannel] = Field(default=None)

    last_contact_at: Optional[datetime] = Field(default=None)
    last_inbound_at: Optional[datetime] = Field(default=None)
    last_outbound_at: Optional[datetime] = Field(default=None)

    messages: List[MessageRecord] = Field(default_factory=list)

    do_not_contact: bool = Field(
        default=False, description="Explicit DNC flag for safety."
    )

    # Retry / delivery tracking (no retry policy logic embedded here)
    send_attempts: int = Field(
        default=0, ge=0, description="Total outbound send attempts across channels."
    )
    last_attempt_at: Optional[datetime] = Field(default=None)
    last_failure_at: Optional[datetime] = Field(default=None)
    consecutive_failures: int = Field(default=0, ge=0)
    retry_scheduled_at: Optional[datetime] = Field(
        default=None, description="When a next retry is scheduled (if any)."
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("do_not_contact")
    def _dnc_implies_status(cls, v, values=None):  # type: ignore[override]
        """
        Keep the schema validation-ready by preventing contradictory combinations.

        This is not business logic; it only enforces consistency between fields.
        """

        # Pydantic v2: values is ValidationInfo; v1: values is dict
        status = None
        try:
            status = getattr(values, "data", None) and values.data.get("status")  # type: ignore[attr-defined]
        except Exception:
            pass
        if status is None and isinstance(values, dict):
            status = values.get("status")

        if v and status not in (CommunicationStatus.DO_NOT_CONTACT, None):
            raise ValueError("do_not_contact=true requires status=do_not_contact")
        return v


class OrchestrationState(_SchemaBase):
    """
    Top-level state container for orchestration.

    This schema is intended to be referenced by the state machine and persisted.
    """

    schema_version: Literal["1.0"] = Field(default=StateSchemaVersion.V1.value)

    id: UUID = Field(..., description="Unique state object id.")
    links: List[StateLink] = Field(
        default_factory=list,
        description="Links to candidate/job/event entities without tight coupling.",
    )

    pipeline: PipelineState = Field(default_factory=PipelineState)
    decision: DecisionState = Field(default_factory=DecisionState)
    communication: CommunicationState = Field(default_factory=CommunicationState)

    transitions: List[StateTransitionRecord] = Field(
        default_factory=list,
        description="Append-only transition audit trail for deterministic state machine validation.",
    )

    audit: StateAudit = Field(default_factory=StateAudit)

    extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Forward-compatible expansion point for cross-cutting fields. "
            "Vertical-slice scoring persistence (flat keys, JSON-serializable): "
            "decision.hard_filter_pass (bool), decision.light_score, decision.light_confidence, "
            "decision.deep_score, decision.deep_confidence (numbers in [0,1]), "
            "decision.evidence_refs (list[str])."
        ),
    )

    @field_validator("schema_version")
    def _schema_version_supported(cls, v):  # type: ignore[override]
        if v != StateSchemaVersion.V1.value:
            raise ValueError(f"Unsupported schema_version: {v}")
        return v

