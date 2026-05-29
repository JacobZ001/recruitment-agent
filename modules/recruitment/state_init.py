"""Deterministic NEW-phase orchestration snapshots for ingress write paths."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from schemas.state_schema import (
    OrchestrationState,
    PipelineState,
    StateAudit,
    StateLink,
)


def initial_orchestration_state(
    *,
    state_id: UUID,
    candidate_id: UUID,
    occurred_at: datetime,
) -> OrchestrationState:
    """Frozen timestamps so replay harnesses can assert identical aggregates across runs."""
    return OrchestrationState(
        id=state_id,
        candidate_id=candidate_id,
        links=[StateLink(kind="candidate", id=candidate_id, source="bootstrap_vertical_slice")],
        pipeline=PipelineState(entered_phase_at=occurred_at),
        audit=StateAudit(
            created_at=occurred_at,
            updated_at=occurred_at,
            updated_by="bootstrap_vertical_slice",
        ),
    )
