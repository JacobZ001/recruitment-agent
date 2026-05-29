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

# Evaluation payloads mirror orchestration evaluation shapes (canonical on Candidate).
from schemas.state_schema import (
    EvaluationState,
    HardFilterEvaluation,
    ScoreEvaluation,
)


class _SchemaBase(BaseModel):
    if _PYDANTIC_V2:
        model_config = ConfigDict(
            extra="forbid",
            validate_assignment=True,
            populate_by_name=True,
        )
    else:

        class Config:  # pragma: no cover
            extra = "forbid"
            validate_assignment = True
            allow_population_by_field_name = True


class CandidateSchemaVersion(str, Enum):
    V1_1 = "1.1"


class ContactMethod(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    TELEGRAM = "telegram"
    LINKEDIN = "linkedin"
    WHATSAPP = "whatsapp"
    OTHER = "other"


class SeniorityLevel(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    UNKNOWN = "unknown"


class WorkAuthorizationStatus(str, Enum):
    AUTHORIZED = "authorized"
    REQUIRES_SPONSORSHIP = "requires_sponsorship"
    UNKNOWN = "unknown"


class Identity(_SchemaBase):
    full_name: Optional[str] = Field(default=None, description="Display name from CV parse.")
    primary_email: Optional[str] = Field(default=None)
    primary_phone: Optional[str] = Field(default=None)
    preferred_contact_method: Optional[ContactMethod] = Field(default=None)
    location: Optional[str] = Field(default=None)
    timezone: Optional[str] = Field(default=None)
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
    compensation_expectation: Optional[str] = Field(default=None)
    availability_date: Optional[date] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class DedupSignals(_SchemaBase):
    normalized_email: Optional[str] = Field(default=None)
    normalized_phone: Optional[str] = Field(default=None)
    cv_content_fingerprint: Optional[str] = Field(
        default=None,
        description="sha256 of normalized extracted CV text from parse ingress.",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class CandidateMetadata(_SchemaBase):
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    updated_by: Optional[str] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)


class TimelineRefs(_SchemaBase):
    event_ids: List[UUID] = Field(default_factory=list)
    correlation_ids: List[UUID] = Field(default_factory=list)
    first_seen_at: Optional[datetime] = Field(default=None)
    last_seen_at: Optional[datetime] = Field(default=None)
    extensions: Dict[str, Any] = Field(default_factory=dict)


# Canonical evaluation home (same nested types as workflow snapshot evaluation).
EvaluationStatus = EvaluationState


class Candidate(_SchemaBase):
    """Central aggregate for candidate business data (R-009 canonical store)."""

    schema_version: Literal["1.1"] = Field(default=CandidateSchemaVersion.V1_1.value)
    candidate_id: UUID = Field(default_factory=uuid4)
    identity: Identity = Field(default_factory=Identity)
    profile: CandidateProfile = Field(default_factory=CandidateProfile)
    evaluation_status: EvaluationStatus = Field(default_factory=EvaluationStatus)
    dedup_signals: DedupSignals = Field(default_factory=DedupSignals)
    timeline: TimelineRefs = Field(default_factory=TimelineRefs)
    metadata: CandidateMetadata = Field(default_factory=CandidateMetadata)
    extensions: Dict[str, Any] = Field(default_factory=dict)
    evaluation_revision: int = Field(
        default=0,
        ge=0,
        description="Monotonic revision bumped on each evaluation_status write.",
    )

    @field_validator("schema_version")
    def _schema_version_supported(cls, v):  # type: ignore[override]
        if v != CandidateSchemaVersion.V1_1.value:
            raise ValueError(f"Unsupported schema_version: {v}")
        return v


def new_candidate(
    candidate_id: UUID,
    *,
    occurred_at: Optional[datetime] = None,
    updated_by: str = "vertical_slice",
) -> Candidate:
    ts = occurred_at or datetime.utcnow()
    return Candidate(
        candidate_id=candidate_id,
        metadata=CandidateMetadata(created_at=ts, updated_at=ts, updated_by=updated_by),
    )


__all__ = (
    "Candidate",
    "CandidateMetadata",
    "CandidateProfile",
    "CandidateSchemaVersion",
    "ContactMethod",
    "DedupSignals",
    "EvaluationStatus",
    "HardFilterEvaluation",
    "Identity",
    "ScoreEvaluation",
    "SeniorityLevel",
    "TimelineRefs",
    "WorkAuthorizationStatus",
    "new_candidate",
)
