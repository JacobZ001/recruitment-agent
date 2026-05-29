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
    Governance-only state: recommendations, human/system outcomes, and audit history.

    This model does not carry scoring/filtering results. Those belong on the
    canonical Candidate aggregate (``evaluation_status``).
    """

    current_outcome: DecisionOutcome = Field(default=DecisionOutcome.UNDECIDED)
    finalized_at: Optional[datetime] = Field(
        default=None, description="When the outcome became final (if applicable)."
    )

    recommendations: List[DecisionRecommendation] = Field(default_factory=list)
    history: List[DecisionRecord] = Field(default_factory=list)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class IngressProfile(_SchemaBase):
    """Structured candidate profile extracted during ingress."""

    years_experience: Optional[int] = Field(default=None, ge=0, le=80)
    seniority: Optional[Literal["junior", "mid", "senior"]] = Field(default=None)
    roles: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    summary: str = Field(default="", description="Single recruiter-facing profile summary.")


class ScoringContextStatus(str, Enum):
    COLLECTING = "collecting"
    READY = "ready"
    STALE = "stale"


class OrganizationContext(_SchemaBase):
    """Organization/company context used to interpret role fit and preference layers."""

    company_name: str = Field(..., min_length=1)
    industry: str = Field(default="")
    team_name: str = Field(default="")
    environment_signals: List[str] = Field(default_factory=list)
    preference_signals: List[str] = Field(default_factory=list)
    summary: str = Field(default="")
    source_refs: List[str] = Field(default_factory=list)


class RecruiterActorContext(_SchemaBase):
    """Context for the specific recruiter or operator authoring the score posture."""

    actor_id: str = Field(..., min_length=1)
    actor_role: str = Field(default="")
    hiring_focus: List[str] = Field(default_factory=list)
    preference_signals: List[str] = Field(default_factory=list)
    avoid_signals: List[str] = Field(default_factory=list)
    summary: str = Field(default="")
    source_refs: List[str] = Field(default_factory=list)


class JobContext(_SchemaBase):
    """Bounded role / requirement / success-signal context for candidate evaluation."""

    title: str = Field(..., min_length=1)
    summary: str = Field(default="")
    responsibilities: List[str] = Field(default_factory=list)
    hard_requirements: List[str] = Field(default_factory=list)
    preferred_requirements: List[str] = Field(default_factory=list)
    success_signals: List[str] = Field(default_factory=list)
    source_refs: List[str] = Field(default_factory=list)


class ScoringContext(_SchemaBase):
    """Canonical evaluation context persisted separately from candidate workflow snapshots."""

    context_version: int = Field(default=1, ge=1)
    status: ScoringContextStatus = Field(default=ScoringContextStatus.COLLECTING)
    organization_authoring_text: str = Field(default="")
    recruiter_actor_authoring_text: str = Field(default="")
    job_authoring_text: str = Field(default="")
    organization_context: Optional[OrganizationContext] = Field(default=None)
    recruiter_actor_context: Optional[RecruiterActorContext] = Field(default=None)
    job_context: Optional[JobContext] = Field(default=None)
    derived_l2_criteria: List[str] = Field(default_factory=list)
    derived_l3_criteria: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    ready_at: Optional[datetime] = Field(default=None)
    stale_at: Optional[datetime] = Field(default=None)
    source_refs: List[str] = Field(default_factory=list)


class CriterionScore(_SchemaBase):
    """Bounded score + confidence pair for one evaluation criterion."""

    score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(default="")


class ScoreLayerEvaluation(_SchemaBase):
    """One explicit scoring layer inside a workflow-stage evaluation."""

    summary: str = Field(default="")
    criteria: Dict[str, CriterionScore] = Field(default_factory=dict)


class HardFilterEvaluation(_SchemaBase):
    """Binary eligibility gate outcome captured as evaluation data."""

    computed_pass: bool
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    explanation: Optional[str] = Field(default=None)
    source: str = Field(..., min_length=1)
    evidence_refs: List[str] = Field(default_factory=list)


class ScoreEvaluation(_SchemaBase):
    """Normalized score payload for light/deep evaluation stages."""

    normalized_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    explanation: str = Field(default="")
    source: str = Field(..., min_length=1)
    context_version: int = Field(..., ge=1)
    stale: bool = Field(default=False)
    l1_universal: ScoreLayerEvaluation = Field(default_factory=ScoreLayerEvaluation)
    l2_role_specific: ScoreLayerEvaluation = Field(default_factory=ScoreLayerEvaluation)
    l3_recruiter_preference: ScoreLayerEvaluation = Field(default_factory=ScoreLayerEvaluation)
    evidence_refs: List[str] = Field(default_factory=list)


class EvaluationState(_SchemaBase):
    """Scoring/filtering payload shape (canonical on Candidate aggregate as of R-009)."""

    hard_filter: Optional[HardFilterEvaluation] = Field(default=None)
    light: Optional[ScoreEvaluation] = Field(default=None)
    deep: Optional[ScoreEvaluation] = Field(default=None)


class EvaluationStatusRef(_SchemaBase):
    """Minimal evaluation snapshot recorded on orchestration state at persist time."""

    revision: int = Field(default=0, ge=0)
    context_version: Optional[int] = Field(default=None, ge=1)
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    score_type: Optional[Literal["light", "deep"]] = Field(default=None)
    stale: bool = Field(default=False)


class IngressFlags(_SchemaBase):
    """Ingress-lifecycle flags derived from deterministic workflow events."""

    was_inactive: bool = Field(default=False)


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
    candidate_id: Optional[UUID] = Field(
        default=None,
        description="Explicit candidate binding (R-009/R-011); required for store index and recruiter read paths.",
    )

    pipeline: PipelineState = Field(default_factory=PipelineState)
    decision: DecisionState = Field(default_factory=DecisionState)
    evaluation_status_ref: Optional[EvaluationStatusRef] = Field(default=None)
    ingress_flags: IngressFlags = Field(default_factory=IngressFlags)
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
            "Do not use as the canonical home for candidate-owned evaluation/profile; those belong "
            "on the Candidate aggregate."
        ),
    )

    @field_validator("schema_version")
    def _schema_version_supported(cls, v):  # type: ignore[override]
        if v != StateSchemaVersion.V1.value:
            raise ValueError(f"Unsupported schema_version: {v}")
        return v

