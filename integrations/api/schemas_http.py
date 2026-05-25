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
            "Other events may carry skill or ranking overrides."
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


class CandidateViewResponse(BaseModel):
    """Recruiter-facing projection from orchestration snapshot (composed read model)."""

    candidate_id: str
    stage: str
    status: CandidateViewStatus
    summary: str
    profile: Optional[Dict[str, Any]] = None
    decision: Dict[str, Any] = Field(default_factory=dict)
    evaluation: Optional[Dict[str, Any]] = None
    flags: Dict[str, Any] = Field(default_factory=dict)
    scores: Dict[str, Any] = Field(default_factory=dict)
    ranking: Dict[str, Any] = Field(default_factory=dict)
    next_actions: List[str] = Field(default_factory=list)


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


class CandidateListItem(BaseModel):
    """Lightweight row for ``GET /candidates`` (latest snapshot per orchestration state)."""

    candidate_id: str
    stage: str
    status: CandidateViewStatus
    overall_score: Optional[CandidateListItemOverallScore] = None
    rank: Optional[int] = None
    total_candidates: Optional[int] = None
    available_actions: List[RecruiterActionItem] = Field(default_factory=list)


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
