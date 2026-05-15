"""Single-process vertical-slice API runtime holder (in-memory bus + store)."""

from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from orchestrator.vertical_slice_planner import VerticalSlicePlanner
from runtime.bootstrap_vertical_slice import (
    VerticalSliceRuntimeBundle,
    _FIXED_CLOCK,
    _initial_state,
    drive_vertical_slice_primary_sequence,
    wire_vertical_slice_runtime,
)
from runtime.in_memory_state_store import InMemoryStateStoreConfig
from runtime.persistence.sqlite_state_store import SQLiteStateStore
from runtime.recording_event_bus import RecordingInMemoryEventBus
from modules.recruitment.exceptions import DemoRunPreconditionError
from schemas.state_schema import OrchestrationState, PipelinePhase


@dataclass(frozen=True)
class DevResetResult:
    """Outcome of :meth:`VerticalSliceApiRuntime.dev_reset_to_bootstrap_initial`."""

    store_revision: int
    pipeline_phase: str
    sqlite_tables_cleared: bool


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

    def dev_reset_to_bootstrap_initial(self) -> DevResetResult:
        """
        Development helper: restore the slice to the same ``OrchestrationState`` as bootstrap
        (pipeline ``NEW``), clear SQLite orchestration tables when applicable, and reset
        ephemeral runtime counters (ingress sequence, recording bus, subscriber history).

        Does not re-wire ids or subscriptions—uses the existing ``state_id`` /
        ``candidate_id`` from :func:`~runtime.bootstrap_vertical_slice.wire_vertical_slice_runtime`.
        """
        with self._lock:
            self._seq = 0
            bus = self.bundle.bus
            if isinstance(bus, RecordingInMemoryEventBus):
                bus.recorded_envelopes.clear()

            sub = self.bundle.subscriber
            sub.last_run = None
            sub.run_history.clear()
            sub.collector.drain()

            init = _initial_state(
                state_id=self.bundle.state_id,
                candidate_id=self.bundle.candidate_id,
                occurred_at=_FIXED_CLOCK,
            )
            store = self.bundle.store
            sqlite_cleared = False
            if isinstance(store, SQLiteStateStore):
                sqlite_cleared = True
                conn = store._conn
                conn.execute("DELETE FROM state_transition_audit")
                conn.execute("DELETE FROM orchestration_state_candidate")
                conn.execute("DELETE FROM orchestration_state")
                try:
                    conn.execute("DELETE FROM sqlite_sequence WHERE name='state_transition_audit'")
                except sqlite3.OperationalError:
                    pass
                conn.commit()
                created = store.create(init)
                if not created.ok or created.meta is None:
                    raise RuntimeError(f"dev reset create failed: {created.failure}")
                rev = created.meta.store_revision
            else:
                got = store.get(self.bundle.state_id)
                if not got.ok or got.snapshot is None or got.meta is None:
                    created = store.create(init)
                    if not created.ok or created.meta is None:
                        raise RuntimeError(f"dev reset create failed: {created.failure}")
                    rev = created.meta.store_revision
                else:
                    rep = store.replace(
                        self.bundle.state_id,
                        init,
                        expected_store_revision=got.meta.store_revision,
                    )
                    if not rep.ok or rep.meta is None:
                        raise RuntimeError(f"dev reset replace failed: {rep.failure}")
                    rev = rep.meta.store_revision

            return DevResetResult(
                store_revision=rev,
                pipeline_phase=init.pipeline.phase.value,
                sqlite_tables_cleared=sqlite_cleared,
            )

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
