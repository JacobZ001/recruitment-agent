"""
In-memory bus that records every ``publish`` envelope (ingress + orchestrator emissions).

Used by replay harnesses and the lightweight API boundary for inspection catalogs—not a
durable event store.
"""

from __future__ import annotations

from typing import Any, List

from interfaces.event_bus_interface import EventEnvelope, PublishResult
from runtime.in_memory_event_bus import InMemoryEventBus


def _snapshot_envelope(envelope: EventEnvelope) -> EventEnvelope:
    """Mutation-safe snapshot for inspection/recording (does not affect bus dispatch)."""
    if hasattr(envelope, "model_copy"):
        return envelope.model_copy(deep=True)
    return envelope.copy(deep=True)  # type: ignore[call-arg]


class RecordingInMemoryEventBus(InMemoryEventBus):
    """Captures every envelope passed to ``publish``."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.recorded_envelopes: List[EventEnvelope] = []

    def publish(self, envelope: EventEnvelope) -> PublishResult:
        self.recorded_envelopes.append(_snapshot_envelope(envelope))
        return super().publish(envelope)
