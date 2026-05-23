"""
Deterministic ingress envelope helpers for recruitment use cases.

Shared clock, envelope builder, and scripted primary progression envelopes.
Vertical-slice wiring lives in ``bootstrap``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, List, Protocol
from uuid import UUID, uuid5

from interfaces.event_bus_interface import EventEnvelope, EventEnvelopeMetadata

from .policies import PRIMARY_VERTICAL_SLICE_EVENT_TYPES

BOOT_NS = UUID("018f3e2a-7c9b-4a3d-8f0e-a11b00c0ffee")
FIXED_CLOCK = datetime(2026, 5, 12, 14, 0, 0, tzinfo=timezone.utc)


def build_ingress_envelope(
    *,
    event_type: str,
    candidate_id: UUID,
    correlation_id: UUID,
    occurred_at: datetime,
    seq: int,
) -> EventEnvelope:
    """Build a deterministic API/bootstrap-style ingress envelope (bootstrap payload keys)."""
    eid = uuid5(BOOT_NS, f"event:{event_type}:{seq}")
    return EventEnvelope(
        event_id=eid,
        event_type=event_type,
        occurred_at=occurred_at,
        subject_id=candidate_id,
        subject_kind="candidate",
        payload={"bootstrap": True, "sequence": seq},
        metadata=EventEnvelopeMetadata(
            correlation_id=correlation_id,
            causation_id=None,
            actor_id="bootstrap_vertical_slice",
        ),
    )


class _ScriptedIngressTarget(Protocol):
    """Minimal bundle/runtime surface for scripted primary ingress envelopes."""

    candidate_id: UUID
    correlation_id: UUID


def vertical_slice_primary_ingress_envelopes(target: _ScriptedIngressTarget) -> List[EventEnvelope]:
    """
    Build deterministic primary progression envelopes (order from :data:`policies.PRIMARY_VERTICAL_SLICE_EVENT_TYPES`).

    Used by demo drivers and inspection catalogs; not an ingress allowlist (see ``policies``).
    """
    return [
        build_ingress_envelope(
            event_type=et,
            candidate_id=target.candidate_id,
            correlation_id=target.correlation_id,
            occurred_at=FIXED_CLOCK,
            seq=seq,
        )
        for seq, et in enumerate(PRIMARY_VERTICAL_SLICE_EVENT_TYPES, start=1)
    ]
