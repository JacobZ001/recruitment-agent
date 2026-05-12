from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, field_validator

    _PYDANTIC_V2 = True
except Exception:  # Pydantic v1 fallback
    from pydantic import validator as field_validator  # type: ignore

    _PYDANTIC_V2 = False


class _SchemaBase(BaseModel):
    """
    Shared schema base (validation-focused only).

    Events are immutable records. Immutability is enforced at the model level.
    """

    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
            frozen=True,
        )
    else:

        class Config:  # pragma: no cover (runtime-selected by Pydantic major version)
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True
            allow_mutation = False


class EventSchemaVersion(str, Enum):
    V1 = "1.0"


class EventType(str, Enum):
    # Candidate lifecycle / intake
    CANDIDATE_CREATED = "candidate_created"
    CV_UPLOADED = "cv_uploaded"
    CV_PARSED = "cv_parsed"

    # Hard filter
    HARD_FILTER_PASSED = "hard_filter_passed"
    HARD_FILTER_FAILED = "hard_filter_failed"

    # Scoring
    LIGHT_SCORING_COMPLETED = "light_scoring_completed"
    DEEP_SCORING_COMPLETED = "deep_scoring_completed"

    # Questionnaire
    QUESTIONNAIRE_REQUESTED = "questionnaire_requested"
    QUESTIONNAIRE_SENT = "questionnaire_sent"
    QUESTIONNAIRE_COMPLETED = "questionnaire_completed"
    QUESTIONNAIRE_FAILED = "questionnaire_failed"

    # Decisions / progression (still as events; decisions remain deterministic elsewhere)
    SHORTLISTED = "shortlisted"
    HUMAN_OVERRIDE = "human_override"

    # Human governance (immutable ingress; deterministic planner interprets)
    RECRUITER_APPROVE_CANDIDATE = "recruiter_approve_candidate"
    RECRUITER_REJECT_CANDIDATE = "recruiter_reject_candidate"
    RECRUITER_SCHEDULE_INTERVIEW = "recruiter_schedule_interview"
    RECRUITER_COMPLETE_INTERVIEW = "recruiter_complete_interview"
    RECRUITER_SEND_OFFER = "recruiter_send_offer"
    RECRUITER_MARK_HIRED = "recruiter_mark_hired"
    RECRUITER_OVERRIDE_TRANSITION = "recruiter_override_transition"
    RECRUITER_FORCE_TRANSITION = "recruiter_force_transition"

    # Interview
    INTERVIEW_SCHEDULED = "interview_scheduled"
    INTERVIEW_COMPLETED = "interview_completed"

    # Offer / closure
    OFFER_SENT = "offer_sent"
    CANDIDATE_REJECTED = "candidate_rejected"

    # Failures (record-only; no retry/routing logic encoded here)
    MESSAGE_DELIVERY_FAILED = "message_delivery_failed"
    EVENT_PROCESSING_FAILED = "event_processing_failed"


class EventSource(str, Enum):
    ORCHESTRATOR = "orchestrator"
    STATE_MACHINE = "state_machine"
    INTEGRATION = "integration"
    HUMAN_OPERATOR = "human_operator"
    SKILL_DETERMINISTIC = "skill_deterministic"
    SKILL_LLM = "skill_llm"
    SYSTEM = "system"


class EventStatus(str, Enum):
    RECORDED = "recorded"
    PROCESSING = "processing"
    APPLIED = "applied"
    IGNORED = "ignored"
    FAILED = "failed"


class EventMetadata(_SchemaBase):
    """
    Auditability + extensibility container.

    Keep raw content out of `metadata` when possible; store references in `payload`.
    """

    trace_id: Optional[str] = Field(
        default=None,
        description="Tracing identifier for observability systems.",
        examples=["trace-01HXYZ...", "dd:1234567890"],
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Incoming request identifier (API gateway, webhook, etc.).",
    )
    actor_id: Optional[str] = Field(
        default=None,
        description="Optional actor identifier (operator username, service id).",
        examples=["human_operator:jane.doe", "integration:telegram", "service:api"],
    )
    actor_ip: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)

    idempotency_key: Optional[str] = Field(
        default=None,
        description="External idempotency key to prevent duplicate event ingestion.",
    )

    extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Forward-compatible expansion point for metadata.",
    )


class OrchestrationEvent(_SchemaBase):
    """
    Immutable event record for orchestration, replay, and audit trails.

    Notes:
    - This schema is intentionally free of routing/orchestration logic.
    - Causation/correlation enable distributed tracing and timeline reconstruction.
    """

    schema_version: Literal["1.0"] = Field(default=EventSchemaVersion.V1.value)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: EventType
    candidate_id: UUID

    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: EventSource
    status: EventStatus = Field(default=EventStatus.RECORDED)

    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Event-specific data (prefer references/keys over raw blobs).",
    )
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    correlation_id: Optional[UUID] = Field(
        default=None,
        description="Groups related events across a workflow/timeline (trace across systems).",
    )
    causation_id: Optional[UUID] = Field(
        default=None,
        description="Parent event that directly caused this event (for replay/debug).",
    )

    @field_validator("schema_version")
    def _schema_version_supported(cls, v):  # type: ignore[override]
        if v != EventSchemaVersion.V1.value:
            raise ValueError(f"Unsupported schema_version: {v}")
        return v
