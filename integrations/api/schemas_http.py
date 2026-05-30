"""HTTP-layer request/response models for the vertical slice API (not domain schemas)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, field_validator

from modules.recruitment.policies import PUBLIC_API_INGRESS_EVENT_TYPES


_ALLOWED_INGRESS = frozenset(PUBLIC_API_INGRESS_EVENT_TYPES)


class VerticalSliceIngressEventBody(BaseModel):
    """Validated ingress payload for ``POST /events``."""

    event_type: str = Field(..., min_length=1)
    candidate_id: Optional[UUID] = Field(
        default=None,
        description="Optional; must match the wired slice candidate when set.",
    )
    correlation_id: Optional[UUID] = Field(default=None)
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Event-specific fields. For ``cv_submitted``, include ``cv_text`` (raw CV body). "
            "Other public `/events` writes are bounded governance ingress only."
        ),
    )

    @field_validator("event_type")
    @classmethod
    def _allowed_event_type(cls, v: str) -> str:
        if v not in _ALLOWED_INGRESS:
            raise ValueError(
                f"event_type must be one of the primary vertical slice ingress types; got {v!r}"
            )
        return v


class StateSummaryResponse(BaseModel):
    pipeline_phase: str
    transitions_count: int
    state_id: str
    store_revision: Optional[int] = None


class CandidatePdfIngressBody(BaseModel):
    """Validated payload for bounded PDF CV upload ingress."""

    pdf_base64: str = Field(
        ...,
        min_length=1,
        description="Raw base64-encoded PDF bytes (no data URL prefix).",
    )
    file_name: str = Field(
        default="cv.pdf",
        min_length=1,
        description="Original uploaded file name; must end with .pdf.",
    )
    correlation_id: Optional[UUID] = Field(default=None)

    @field_validator("file_name")
    @classmethod
    def _pdf_file_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("file_name must be non-empty")
        if not name.lower().endswith(".pdf"):
            raise ValueError("file_name must end with .pdf")
        return name


class OrganizationContextBody(BaseModel):
    raw_text: str = Field(..., min_length=1)
    source_ref: Optional[str] = Field(default=None)


class RecruiterActorContextBody(BaseModel):
    raw_text: str = Field(..., min_length=1)
    source_ref: Optional[str] = Field(default=None)


class JobContextTextBody(BaseModel):
    raw_text: str = Field(..., min_length=1)
    source_ref: Optional[str] = Field(default=None)


class JobContextPdfBody(CandidatePdfIngressBody):
    pass


class RecruiterJobAnswersBody(BaseModel):
    role_title: str = Field(..., min_length=1)
    must_haves_answer: str = Field(default="")
    preferred_answer: str = Field(default="")
    success_answer: str = Field(default="")
    responsibilities_answer: str = Field(default="")


class ScoringContextResponse(BaseModel):
    context_version: int
    status: str
    organization_authoring_text: str = Field(default="")
    recruiter_actor_authoring_text: str = Field(default="")
    job_authoring_text: str = Field(default="")
    organization_context: Optional[Dict[str, Any]] = None
    recruiter_actor_context: Optional[Dict[str, Any]] = None
    job_context: Optional[Dict[str, Any]] = None
    derived_l2_criteria: List[str] = Field(default_factory=list)
    derived_l3_criteria: List[str] = Field(default_factory=list)
    created_at: str
    updated_at: str
    ready_at: Optional[str] = None
    last_ready_materialized_fingerprint: Optional[str] = None
    source_refs: List[str] = Field(default_factory=list)
    materialization_blockers: List[str] = Field(default_factory=list)


class TimelineResponse(BaseModel):
    timeline_text: str
    catalog_note: Optional[str] = Field(
        default=None,
        description="Bounded notice when timeline catalog coverage is uncertain.",
    )


class HealthResponse(BaseModel):
    status: str
    runtime: str
    sync: bool
    auth: str


class EventIngressResponse(BaseModel):
    ingress_accepted: bool
    publish_status: str
    event_id: str
    event_type: str
    publish_result: Dict[str, Any]
    state_summary: Optional[StateSummaryResponse] = None


class CandidateDedupIngressSummary(BaseModel):
    status: str
    pending_resolution: bool
    matches: List[Dict[str, Any]] = Field(default_factory=list)


class CandidateCreatePdfIngressResponse(EventIngressResponse):
    """``POST /candidates/cv/pdf`` — server-assigned candidate + ingress outcome."""

    candidate_id: str
    dedup: Optional[CandidateDedupIngressSummary] = None


class DemoCandidateResponse(BaseModel):
    """Demo fixture profile plus current slice snapshot (inspection-oriented, not a domain aggregate)."""

    candidate_id: str
    profile: Dict[str, Any] = Field(default_factory=dict)
    pipeline_phase: Optional[str] = None
    state_summary: Optional[StateSummaryResponse] = None
    skill_summaries: Dict[str, Any] = Field(default_factory=dict)
    inactive_reason: Optional[str] = Field(
        default=None,
        description="From orchestration snapshot extensions when present (e.g. after ranking reject).",
    )


class CandidateViewStatus(BaseModel):
    """Aggregate lifecycle bucket: ``active`` | ``inactive`` | ``hired`` (derived from pipeline phase only)."""

    kind: str


class CandidateGovernanceFlags(BaseModel):
    ingress_in_progress: bool = False
    orphan_ingress: bool = False
    dedup_status: Optional[str] = None
    dedup_pending_resolution: bool = False
    dedup_linked_to_candidate_id: Optional[str] = None
    dedup_match_count: Optional[int] = None


class CandidateProfile(BaseModel):
    """
    Recruiter-facing profile DTO (not the aggregate ``schemas.candidate_schema.Candidate``).

    Maps from canonical Candidate identity + profile via projection.
    """

    full_name: Optional[str] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    preferred_contact_method: Optional[str] = None
    location: Optional[str] = None
    timezone: Optional[str] = None
    external_profile_urls: List[str] = Field(default_factory=list)
    headline: Optional[str] = None
    summary: str = Field(default="")
    seniority: Optional[str] = Field(default=None, description='One of: "junior" | "mid" | "senior"')
    years_experience: Optional[float] = Field(default=None, ge=0)
    languages: List[str] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    industries: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)
    work_authorization: Optional[str] = None
    compensation_expectation: Optional[str] = None
    availability_date: Optional[str] = None
    extensions: Dict[str, Any] = Field(default_factory=dict)


class CandidateViewResponse(BaseModel):
    """Recruiter-facing projection from orchestration snapshot (composed read model)."""

    candidate_id: str
    stage: str
    status: CandidateViewStatus
    summary: str
    profile: Optional[CandidateProfile] = None
    decision: Dict[str, Any] = Field(default_factory=dict)
    evaluation: Optional[Dict[str, Any]] = None
    scoring_context: Optional[Dict[str, Any]] = None
    flags: Dict[str, Any] = Field(default_factory=dict)
    scores: Dict[str, Any] = Field(default_factory=dict)
    ranking: Dict[str, Any] = Field(default_factory=dict)
    available_actions: List["RecruiterActionItem"] = Field(default_factory=list)
    next_actions: List[str] = Field(default_factory=list)
    governance_flags: CandidateGovernanceFlags = Field(default_factory=CandidateGovernanceFlags)


class CandidateListItemOverallScore(BaseModel):
    value: Optional[float] = None
    type: Optional[str] = Field(
        default=None,
        description='Score source when present: "light" or "deep" (aligned with GET /candidate).',
    )


class RecruiterActionItem(BaseModel):
    key: str
    label: str
    event_type: str
    group: str
    order: int


class CandidateListItem(BaseModel):
    """Lightweight row for ``GET /candidates`` (latest snapshot per orchestration state)."""

    candidate_id: str
    full_name: str = Field(default="", description="Display name from canonical Candidate identity.")
    stage: str
    status: CandidateViewStatus
    headline: str = Field(
        default="",
        description="Human-friendly label from canonical Candidate profile (headline or full name).",
    )
    summary: str = Field(default="", description="Candidate summary snippet for list display.")
    top_skills: List[str] = Field(default_factory=list, description="Top skills for list display.")
    overall_score: Optional[CandidateListItemOverallScore] = None
    rank: Optional[int] = None
    total_candidates: Optional[int] = None
    available_actions: List[RecruiterActionItem] = Field(default_factory=list)
    governance_flags: CandidateGovernanceFlags = Field(default_factory=CandidateGovernanceFlags)


class DedupGovernanceBody(BaseModel):
    actor_id: str = Field(..., min_length=1)
    reason: str = Field(..., min_length=1)


class DedupLinkBody(DedupGovernanceBody):
    target_candidate_id: UUID


class CandidateActionBody(BaseModel):
    """Recruiter governance ingress for ``POST /candidates/{candidate_id}/action``."""

    event_type: str = Field(
        ...,
        min_length=1,
        validation_alias=AliasChoices("event_type", "action"),
        description="Governance event type (e.g. recruiter_schedule_interview). ``action`` is a deprecated alias.",
    )
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional governance fields merged over API defaults (actor_id, reason, etc.).",
    )


class DemoRunResponse(BaseModel):
    """Result of publishing the scripted primary sequence via the bus."""

    message: str
    state_summary: StateSummaryResponse


class AdminResetResponse(BaseModel):
    """Result of ``POST /admin/reset`` (development convenience; no authentication)."""

    status: str = "ok"
    message: str = "vertical slice reset to bootstrap initial state"
    store_revision: int
    pipeline_phase: str
    sqlite_tables_cleared: bool = Field(
        description="True when SQLite orchestration tables were truncated before re-seeding.",
    )
