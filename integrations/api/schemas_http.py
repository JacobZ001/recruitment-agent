"""HTTP-layer request/response models for the vertical slice API (not domain schemas)."""

from __future__ import annotations

from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from runtime.bootstrap_vertical_slice import PRIMARY_VERTICAL_SLICE_EVENT_TYPES


_ALLOWED_INGRESS = frozenset(PRIMARY_VERTICAL_SLICE_EVENT_TYPES)


class VerticalSliceIngressEventBody(BaseModel):
    """Validated ingress payload for ``POST /events``."""

    event_type: str = Field(..., min_length=1)
    candidate_id: Optional[UUID] = Field(
        default=None,
        description="Optional; must match the wired slice candidate when set.",
    )
    correlation_id: Optional[UUID] = Field(default=None)
    payload: Dict[str, Any] = Field(default_factory=dict)

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
