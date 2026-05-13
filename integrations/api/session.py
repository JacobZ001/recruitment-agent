"""Single-process vertical-slice API runtime holder (in-memory bus + store)."""

from __future__ import annotations

import threading
from typing import Optional
from uuid import UUID

from orchestrator.vertical_slice_planner import VerticalSlicePlanner
from runtime.bootstrap_vertical_slice import (
    VerticalSliceRuntimeBundle,
    drive_vertical_slice_primary_sequence,
    wire_vertical_slice_runtime,
)
from runtime.in_memory_state_store import InMemoryStateStoreConfig
from runtime.persistence.sqlite_state_store import SQLiteStateStore
from runtime.recording_event_bus import RecordingInMemoryEventBus
from schemas.state_schema import OrchestrationState, PipelinePhase


class DemoRunPreconditionError(ValueError):
    """Raised when ``POST /demo/run`` cannot safely replay the scripted primary sequence."""


class VerticalSliceApiRuntime:
    """
    One wired vertical slice per process: deterministic ids, recording bus for inspection.

    Not multi-tenant; ``candidate_id`` on the bundle matches
    ``VERTICAL_SLICE_DEFAULT_CANDIDATE_ID``.
    """

    def __init__(self, *, db_path: Optional[str] = None) -> None:
        if db_path is not None:
            sql_store = SQLiteStateStore(db_path, config=InMemoryStateStoreConfig())
            self.bundle: VerticalSliceRuntimeBundle = wire_vertical_slice_runtime(
                bus=RecordingInMemoryEventBus(),
                planner=VerticalSlicePlanner(demo_skill_context=True),
                store=sql_store,
            )
        else:
            self.bundle = wire_vertical_slice_runtime(
                bus=RecordingInMemoryEventBus(),
                planner=VerticalSlicePlanner(demo_skill_context=True),
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

    def run_primary_demo_sequence(self) -> OrchestrationState:
        """
        Publish the canonical primary ingress sequence via the bus (same as bootstrap CLI).

        Requires pipeline phase ``NEW`` so the scripted envelopes align with transition
        preconditions; callers that already advanced the slice should use ``POST /events``.
        """
        with self._lock:
            got = self.bundle.store.get(self.bundle.state_id)
            if not got.ok or got.snapshot is None:
                raise DemoRunPreconditionError("orchestration state missing")
            if got.snapshot.pipeline.phase != PipelinePhase.NEW:
                raise DemoRunPreconditionError(
                    "demo run requires pipeline_phase NEW; use POST /events for partial progression"
                )
            return drive_vertical_slice_primary_sequence(self.bundle)
