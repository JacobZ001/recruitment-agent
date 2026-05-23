"""
Synchronous in-memory orchestration state snapshot runtime.

Purpose
-------
Hold **canonical** :class:`~schemas.state_schema.OrchestrationState` snapshots for
vertical-slice runs, local tests, and deterministic workflow wiring. This is a
**control-plane convenience**, not persistence: process-local only, no database,
no transactions, no event sourcing.

Immutable snapshot philosophy
-----------------------------
Callers pass Pydantic-validated ``OrchestrationState`` instances produced by the
orchestrator (or other deterministic writers). The store **never mutates** a
retained snapshot in place: it keeps deep copies and returns deep copies so
downstream reads observe stable facts. Progression is modeled as **explicit
replacement** of one snapshot with the next (append-only transition history lives
*inside* the schema, not in the store).

Runtime boundaries
------------------
- **In scope**: keyed CRUD-style access by ``OrchestrationState.id``, optional
  candidate lookup via ``StateLink`` (``kind`` case-insensitive ``"candidate"``;
  if multiple candidate links exist, each id maps to this state id, with last
  write winning in the index—vertical slice assumes one primary candidate per state),
  optimistic ``store_revision`` checks, bounded capacity, injectable clock for tests.
- **Out of scope**: SQL/ORM, distributed cache, locking, async, MVCC across
  processes, replay log ingestion, transition validation (that belongs to
  :class:`state_machine.transition_engine.TransitionEngine` before the snapshot
  is committed here).

Relationship to orchestrator / transition engine
------------------------------------------------
The **transition engine** validates whether a move is legal; the **orchestrator**
applies validated progression and emits the next ``OrchestrationState``. The store
only **remembers** the latest snapshot the application chooses to save—it does not
re-run guards or infer transitions. Keeping that split preserves ADR-001 control
vs. cognition boundaries.

Replay expectations
---------------------
Replay tooling (future) will typically **rehydrate** state by re-applying events or
replaying orchestration steps; this store can still serve **harness** and **demo**
modes where a frozen clock + scripted ``replace`` calls reproduce timelines. The
optional ``replay_run_id`` field on metadata is a forward-compatible hook for
callers to tag writes without the store interpreting replay semantics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
from uuid import UUID

from pydantic import BaseModel, Field

try:  # Pydantic v2
    from pydantic import ConfigDict, model_validator

    _PYDANTIC_V2 = True
except Exception:  # Pydantic v1 fallback
    from pydantic import root_validator  # type: ignore

    _PYDANTIC_V2 = False

from schemas.state_schema import OrchestrationState, StateLink


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _state_deep_copy(state: OrchestrationState) -> OrchestrationState:
    if _PYDANTIC_V2:
        return state.model_copy(deep=True)
    return state.copy(deep=True)  # type: ignore[call-arg]


class _RuntimeBase(BaseModel):
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


class StateStoreFailureCode(str, Enum):
    """Stable taxonomy for store-level failures (audit/harness friendly)."""

    NOT_FOUND = "not_found"
    ALREADY_EXISTS = "already_exists"
    REVISION_MISMATCH = "revision_mismatch"
    STATE_ID_MISMATCH = "state_id_mismatch"
    CAPACITY_EXCEEDED = "capacity_exceeded"


class StateStoreFailure(_RuntimeBase):
    code: StateStoreFailureCode
    message: str = Field(..., min_length=1)
    details: Dict[str, Any] = Field(default_factory=dict)


class StateStoreSnapshotMeta(_RuntimeBase):
    """
    Lightweight runtime metadata for one retained snapshot generation.

    ``store_revision`` is monotonic per ``state_id`` for this process (starts at 1
    on create, increments on each successful replace). It is **not** a schema field
    on ``OrchestrationState``; callers may use it for optimistic concurrency.
    """

    state_id: UUID
    store_revision: int = Field(..., ge=1)
    recorded_at: datetime = Field(..., description="UTC timestamp from the store clock.")
    replay_run_id: Optional[UUID] = Field(
        default=None,
        description="Optional caller-supplied replay correlation (store does not interpret it).",
    )
    extensions: Dict[str, Any] = Field(default_factory=dict)


class StateStoreResult(_RuntimeBase):
    """
    Uniform outcome for get/create/replace operations.

    On success, ``snapshot`` is always a **deep copy** of the retained row (callers
    may mutate it without affecting the store). ``meta`` describes the generation
    returned from the store clock at write/read time for that revision.
    """

    ok: bool
    failure: Optional[StateStoreFailure] = None
    snapshot: Optional[OrchestrationState] = None
    meta: Optional[StateStoreSnapshotMeta] = None

    if _PYDANTIC_V2:

        @model_validator(mode="after")
        def _invariants(self):  # type: ignore[override]
            if self.ok and self.failure is not None:
                raise ValueError("ok=true forbids failure")
            if not self.ok and self.failure is None:
                raise ValueError("ok=false requires failure")
            if self.ok and self.snapshot is None:
                raise ValueError("ok=true requires snapshot for this store API")
            if not self.ok and self.snapshot is not None:
                raise ValueError("ok=false forbids snapshot")
            if self.ok and self.meta is None:
                raise ValueError("ok=true requires meta")
            if not self.ok and self.meta is not None:
                raise ValueError("ok=false forbids meta")
            return self

    else:

        @root_validator
        def _invariants(cls, values):  # type: ignore[override]
            ok = values.get("ok")
            if ok and values.get("failure") is not None:
                raise ValueError("ok=true forbids failure")
            if not ok and values.get("failure") is None:
                raise ValueError("ok=false requires failure")
            if ok and values.get("snapshot") is None:
                raise ValueError("ok=true requires snapshot for this store API")
            if not ok and values.get("snapshot") is not None:
                raise ValueError("ok=false forbids snapshot")
            if ok and values.get("meta") is None:
                raise ValueError("ok=true requires meta")
            if not ok and values.get("meta") is not None:
                raise ValueError("ok=false forbids meta")
            return values


class InMemoryStateStoreLimits(_RuntimeBase):
    max_distinct_states: int = Field(default=10_000, ge=1)


@dataclass
class InMemoryStateStoreConfig:
    """
    Process-local configuration.

    ``clock`` defaults to UTC wall clock; tests may inject a deterministic callable.
    """

    clock: Callable[[], datetime] = field(default_factory=lambda: _utc_now)
    limits: InMemoryStateStoreLimits = field(default_factory=InMemoryStateStoreLimits)


def _candidate_ids_from_links(links: List[StateLink]) -> List[UUID]:
    out: List[UUID] = []
    for link in links:
        if link.kind.strip().lower() == "candidate":
            out.append(link.id)
    return out


class InMemoryStateStore:
    """
    Single-process synchronous snapshot bag keyed by ``OrchestrationState.id``.

    Not thread-safe; callers must serialize concurrent access if needed.
    """

    def __init__(self, config: Optional[InMemoryStateStoreConfig] = None) -> None:
        self._config = config or InMemoryStateStoreConfig()
        # state_id -> (deep snapshot, store_revision)
        self._rows: Dict[UUID, Tuple[OrchestrationState, int]] = {}
        self._candidate_index: Dict[UUID, UUID] = {}

    def exists(self, state_id: UUID) -> bool:
        return state_id in self._rows

    def has_candidate(self, candidate_id: UUID) -> bool:
        return candidate_id in self._candidate_index

    def list_all_state_ids(self) -> List[UUID]:
        """Return all persisted orchestration state ids (deterministic sort order)."""
        return sorted(self._rows.keys(), key=lambda sid: str(sid))

    def get(self, state_id: UUID, *, replay_run_id: Optional[UUID] = None) -> StateStoreResult:
        row = self._rows.get(state_id)
        if row is None:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.NOT_FOUND,
                    message="No orchestration snapshot exists for the given state id",
                    details={"state_id": str(state_id)},
                ),
            )
        snap, rev = row
        now = self._config.clock()
        return StateStoreResult(
            ok=True,
            snapshot=_state_deep_copy(snap),
            meta=StateStoreSnapshotMeta(
                state_id=state_id,
                store_revision=rev,
                recorded_at=now,
                replay_run_id=replay_run_id,
            ),
        )

    def get_for_candidate(
        self, candidate_id: UUID, *, replay_run_id: Optional[UUID] = None
    ) -> StateStoreResult:
        sid = self._candidate_index.get(candidate_id)
        if sid is None:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.NOT_FOUND,
                    message="No orchestration snapshot is indexed for the given candidate id",
                    details={"candidate_id": str(candidate_id)},
                ),
            )
        return self.get(sid, replay_run_id=replay_run_id)

    def create(
        self,
        snapshot: OrchestrationState,
        *,
        replay_run_id: Optional[UUID] = None,
    ) -> StateStoreResult:
        sid = snapshot.id
        if sid in self._rows:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.ALREADY_EXISTS,
                    message="An orchestration snapshot already exists for this state id",
                    details={"state_id": str(sid)},
                ),
            )
        if len(self._rows) >= self._config.limits.max_distinct_states:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.CAPACITY_EXCEEDED,
                    message="max_distinct_states reached",
                    details={"limit": self._config.limits.max_distinct_states},
                ),
            )

        frozen = _state_deep_copy(snapshot)
        self._rows[sid] = (frozen, 1)
        self._reindex_candidates_for_state(sid, frozen)

        now = self._config.clock()
        return StateStoreResult(
            ok=True,
            snapshot=_state_deep_copy(frozen),
            meta=StateStoreSnapshotMeta(
                state_id=sid,
                store_revision=1,
                recorded_at=now,
                replay_run_id=replay_run_id,
            ),
        )

    def replace(
        self,
        state_id: UUID,
        snapshot: OrchestrationState,
        *,
        expected_store_revision: Optional[int] = None,
        replay_run_id: Optional[UUID] = None,
    ) -> StateStoreResult:
        if snapshot.id != state_id:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.STATE_ID_MISMATCH,
                    message="Snapshot id must match the state_id key",
                    details={"state_id": str(state_id), "snapshot_id": str(snapshot.id)},
                ),
            )

        row = self._rows.get(state_id)
        if row is None:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.NOT_FOUND,
                    message="Cannot replace: no existing snapshot for state id",
                    details={"state_id": str(state_id)},
                ),
            )

        _snap, rev = row
        if expected_store_revision is not None and expected_store_revision != rev:
            return StateStoreResult(
                ok=False,
                failure=StateStoreFailure(
                    code=StateStoreFailureCode.REVISION_MISMATCH,
                    message="Optimistic store revision mismatch",
                    details={
                        "state_id": str(state_id),
                        "expected": expected_store_revision,
                        "actual": rev,
                    },
                ),
            )

        new_rev = rev + 1
        frozen = _state_deep_copy(snapshot)
        self._unindex_candidates_for_state(state_id)
        self._rows[state_id] = (frozen, new_rev)
        self._reindex_candidates_for_state(state_id, frozen)

        now = self._config.clock()
        return StateStoreResult(
            ok=True,
            snapshot=_state_deep_copy(frozen),
            meta=StateStoreSnapshotMeta(
                state_id=state_id,
                store_revision=new_rev,
                recorded_at=now,
                replay_run_id=replay_run_id,
            ),
        )

    def _unindex_candidates_for_state(self, state_id: UUID) -> None:
        to_drop = [cid for cid, sid in self._candidate_index.items() if sid == state_id]
        for cid in to_drop:
            del self._candidate_index[cid]

    def _reindex_candidates_for_state(self, state_id: UUID, snapshot: OrchestrationState) -> None:
        for cid in _candidate_ids_from_links(list(snapshot.links)):
            self._candidate_index[cid] = state_id
