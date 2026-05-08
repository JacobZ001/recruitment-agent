from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Literal, Optional
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

    This file defines the central Candidate aggregate. It intentionally does not
    encode orchestration/routing/ranking logic; it is a typed data contract.
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


class CandidateSchemaVersion(str, Enum):
    V1 = "1.0"


class CandidateStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class ContactMethod(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    TELEGRAM = "telegram"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class SeniorityLevel(str, Enum):
    INTERN = "intern"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    MANAGER = "manager"
    DIRECTOR = "director"
    VP = "vp"
    C_LEVEL = "c_level"
    UNKNOWN = "unknown"


class WorkAuthorizationStatus(str, Enum):
    AUTHORIZED = "authorized"
    REQUIRES_SPONSORSHIP = "requires_sponsorship"
    UNKNOWN = "unknown"


class ConfidenceLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class EvidenceKind(str, Enum):
    CV = "cv"
    COVER_LETTER = "cover_letter"
    QUESTIONNAIRE = "questionnaire"
    INTERVIEW_NOTES = "interview_notes"
    PORTFOLIO = "portfolio"
    LINK = "link"
    MESSAGE = "message"
    OTHER = "other"


class RiskSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskIndicatorType(str, Enum):
    INCONSISTENT_DATES = "inconsistent_dates"
    EMPLOYMENT_GAP = "employment_gap"
    UNVERIFIED_CLAIMS = "unverified_claims"
    COMMUNICATION_RED_FLAG = "communication_red_flag"
    INTEGRITY_CONCERN = "integrity_concern"
    COMPENSATION_MISMATCH = "compensation_mismatch"
    OTHER = "other"


class ScoreDimension(str, Enum):
    COMMUNICATION = "communication"
    OWNERSHIP = "ownership"
    RELIABILITY = "reliability"
    THINKING_CLARITY = "thinking_clarity"
    ROLE_FIT = "role_fit"
    EXECUTIVE_MATURITY = "executive_maturity"
    RISK = "risk"
    OVERALL = "overall"


class ScoreSource(str, Enum):
    DETERMINISTIC = "deterministic"
    LLM = "llm"
    HUMAN = "human"


class Identity(_SchemaBase):
    full_name: Optional[str] = Field(default=None, description="Display name.")
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)

    primary_email: Optional[str] = Field(default=None)
    primary_phone: Optional[str] = Field(default=None)
    preferred_contact_method: Optional[ContactMethod] = Field(default=None)

    location: Optional[str] = Field(default=None, description="Free-form location.")
    timezone: Optional[str] = Field(default=None, description="IANA timezone if known.")

    external_profile_urls: List[str] = Field(default_factory=list)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class CandidateProfile(_SchemaBase):
    headline: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)

    seniority: SeniorityLevel = Field(default=SeniorityLevel.UNKNOWN)
    years_experience: Optional[float] = Field(default=None, ge=0)

    languages: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)

    work_authorization: WorkAuthorizationStatus = Field(
        default=WorkAuthorizationStatus.UNKNOWN
    )
    compensation_expectation: Optional[str] = Field(
        default=None, description="Free-form; keep numeric normalization elsewhere."
    )

    availability_date: Optional[date] = Field(default=None)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class ArtifactRef(_SchemaBase):
    """
    Reference to stored artifacts (CV files, parsed outputs, transcripts, etc.).
    """

    kind: EvidenceKind
    ref: str = Field(
        ...,
        min_length=1,
        description="Storage key/URI/reference. Avoid embedding large blobs in schemas.",
    )
    sha256: Optional[str] = Field(
        default=None,
        description="Optional content hash for deduplication/integrity checks.",
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class ResumeCV(_SchemaBase):
    """
    Structured CV area. Keep raw text in artifacts referenced by `artifacts`.
    """

    artifacts: List[ArtifactRef] = Field(default_factory=list)

    parsed_summary_ref: Optional[str] = Field(
        default=None,
        description="Reference to structured parsing output (not embedded here).",
    )
    parsed_at: Optional[datetime] = Field(default=None)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class OrchestrationStateRef(_SchemaBase):
    """
    Reference/snapshot hook to the orchestration state.

    Note: The canonical, importable `OrchestrationState` is defined in
    `schemas/state_schema.py` (treat this as a contract reference; avoid cross-schema imports here).
    """

    state_id: UUID
    schema_version: Literal["1.0"] = Field(default="1.0")

    snapshot: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional embedded snapshot for read models/debugging (validated elsewhere).",
    )
    last_event_id: Optional[UUID] = Field(
        default=None, description="Most recent event applied to this state."
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)


class ScoreRecord(_SchemaBase):
    dimension: ScoreDimension
    value: float = Field(..., ge=0.0, le=1.0, description="Normalized score in [0, 1].")
    source: ScoreSource

    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    rationale_ref: Optional[str] = Field(
        default=None, description="Reference key to stored explanation/rationale."
    )
    evidence_refs: List[str] = Field(
        default_factory=list,
        description="References/keys to structured evidence supporting this score.",
    )

    model_version: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class CandidateConfidence(_SchemaBase):
    """
    Confidence model for explainability and adaptive data collection.
    """

    overall: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    level: Optional[ConfidenceLevel] = Field(default=None)

    per_section: Dict[str, float] = Field(
        default_factory=dict,
        description="Section -> confidence in [0, 1] (e.g. 'profile', 'cv', 'scores').",
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("per_section")
    def _per_section_confidence_in_range(cls, v: Dict[str, float]):  # type: ignore[override]
        for k, val in v.items():
            if not k:
                raise ValueError("per_section keys must be non-empty")
            if val < 0.0 or val > 1.0:
                raise ValueError("per_section confidence values must be in [0, 1]")
        return v


class RecruiterFeedback(_SchemaBase):
    """
    Human feedback used for calibration and preference alignment.
    """

    recruiter_id: Optional[str] = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    notes_ref: Optional[str] = Field(
        default=None, description="Reference key to stored feedback notes."
    )
    adjustments: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured adjustments (e.g. score tweaks) recorded for calibration.",
    )
    evidence_refs: List[str] = Field(default_factory=list)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class HumanDecision(_SchemaBase):
    """
    Human decision records (distinct from deterministic state machine transitions).
    """

    decision_type: str = Field(
        ...,
        min_length=1,
        description=(
            "Temporary string vocabulary. This is intentionally kept as `str` to avoid "
            "premature enum fragmentation across schemas. A dedicated architecture step "
            "will consolidate shared domain vocabulary into reusable shared enums."
        ),
    )
    outcome: str = Field(..., min_length=1)
    decided_by: Optional[str] = Field(default=None)
    decided_at: datetime = Field(default_factory=datetime.utcnow)

    reason_ref: Optional[str] = Field(
        default=None, description="Reference key to stored decision rationale."
    )
    evidence_refs: List[str] = Field(default_factory=list)

    event_id: Optional[UUID] = Field(
        default=None, description="Associated event id, if the decision produced an event."
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)


class TimelineRefs(_SchemaBase):
    """
    References for reconstructing a timeline without embedding event records.
    """

    event_ids: List[UUID] = Field(default_factory=list)
    correlation_ids: List[UUID] = Field(default_factory=list)

    first_seen_at: Optional[datetime] = Field(default=None)
    last_seen_at: Optional[datetime] = Field(default=None)

    extensions: Dict[str, Any] = Field(default_factory=dict)


class RiskIndicator(_SchemaBase):
    kind: RiskIndicatorType
    severity: RiskSeverity
    description_ref: Optional[str] = Field(
        default=None, description="Reference key to stored risk explanation."
    )
    evidence_refs: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class DeduplicationKeys(_SchemaBase):
    """
    Deterministic identifiers used for deduplication.
    """

    canonical_email: Optional[str] = Field(default=None)
    canonical_phone: Optional[str] = Field(default=None)
    external_ids: Dict[str, str] = Field(
        default_factory=dict,
        description="Namespace -> external id (e.g. {'telegram': '123', 'linkedin': '...'}).",
    )
    content_fingerprints: List[str] = Field(
        default_factory=list,
        description="Stable fingerprints/hashes of artifacts (e.g. cv sha256).",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class CandidateMetadata(_SchemaBase):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Maintained by orchestrator/service layer; the schema does not auto-update timestamps.",
    )
    updated_by: Optional[str] = Field(default=None)

    status: CandidateStatus = Field(default=CandidateStatus.ACTIVE)

    tags: List[str] = Field(default_factory=list, description="Talent pool labels.")
    pool_segments: List[str] = Field(
        default_factory=list, description="Segments for future talent matching."
    )

    recruiter_memory_refs: List[str] = Field(
        default_factory=list,
        description="References to recruiter preference/memory artifacts used for alignment.",
    )

    extensions: Dict[str, Any] = Field(default_factory=dict)


class Candidate(_SchemaBase):
    """
    Central aggregate entity for recruitment orchestration.
    """

    schema_version: Literal["1.0"] = Field(default=CandidateSchemaVersion.V1.value)

    candidate_id: UUID = Field(default_factory=uuid4)

    identity: Identity = Field(default_factory=Identity)
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    resume_cv: ResumeCV = Field(default_factory=ResumeCV)

    orchestration_state: Optional[OrchestrationStateRef] = Field(
        default=None,
        description="Reference/snapshot hook to the canonical orchestration state schema.",
    )

    scores: List[ScoreRecord] = Field(default_factory=list)
    confidence: CandidateConfidence = Field(default_factory=CandidateConfidence)

    recruiter_feedback: List[RecruiterFeedback] = Field(default_factory=list)
    human_decisions: List[HumanDecision] = Field(default_factory=list)

    timeline: TimelineRefs = Field(default_factory=TimelineRefs)
    risk_indicators: List[RiskIndicator] = Field(default_factory=list)

    deduplication: DeduplicationKeys = Field(default_factory=DeduplicationKeys)

    metadata: CandidateMetadata = Field(default_factory=CandidateMetadata)

    extensions: Dict[str, Any] = Field(
        default_factory=dict,
        description="Forward-compatible expansion point for cross-cutting fields.",
    )

    @field_validator("schema_version")
    def _schema_version_supported(cls, v):  # type: ignore[override]
        if v != CandidateSchemaVersion.V1.value:
            raise ValueError(f"Unsupported schema_version: {v}")
        return v

