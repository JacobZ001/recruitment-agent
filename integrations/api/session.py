"""Single-process vertical-slice API runtime holder (in-memory bus + store)."""

from __future__ import annotations

import threading
from uuid import UUID

from runtime.bootstrap_vertical_slice import VerticalSliceRuntimeBundle, wire_vertical_slice_runtime
from runtime.recording_event_bus import RecordingInMemoryEventBus


class VerticalSliceApiRuntime:
    """
    One wired vertical slice per process: deterministic ids, recording bus for inspection.

    Not multi-tenant; ``candidate_id`` on the bundle matches
    ``VERTICAL_SLICE_DEFAULT_CANDIDATE_ID``.
    """

    def __init__(self) -> None:
        self.bundle: VerticalSliceRuntimeBundle = wire_vertical_slice_runtime(
            bus=RecordingInMemoryEventBus(),
        )
        self._seq = 0
        self._lock = threading.Lock()

    @property
    def candidate_id(self) -> UUID:
        return self.bundle.candidate_id

    @property
    def state_id(self) -> UUID:
        return self.bundle.state_id

    def next_publish_sequence(self) -> int:
        with self._lock:
            self._seq += 1
            return self._seq
