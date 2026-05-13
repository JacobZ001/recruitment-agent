"""SQLite orchestration state store: API parity with InMemoryStateStore + wiring survival."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from runtime.bootstrap_vertical_slice import (
    _FIXED_CLOCK,
    drive_vertical_slice_primary_sequence,
    wire_vertical_slice_runtime,
)
from runtime.in_memory_state_store import (
    InMemoryStateStoreConfig,
    InMemoryStateStoreLimits,
    StateStoreFailureCode,
)
from runtime.persistence.sqlite_state_store import SQLiteStateStore
from schemas.state_schema import (
    OrchestrationState,
    PipelinePhase,
    PipelineState,
    StateAudit,
    StateLink,
)
from tests.replay.recording_bus import RecordingInMemoryEventBus


def _minimal_state(*, state_id, candidate_id, phase: PipelinePhase = PipelinePhase.NEW) -> OrchestrationState:
    return OrchestrationState(
        id=state_id,
        links=[StateLink(kind="candidate", id=candidate_id, source="test")],
        pipeline=PipelineState(phase=phase, entered_phase_at=_FIXED_CLOCK),
        audit=StateAudit(
            created_at=_FIXED_CLOCK,
            updated_at=_FIXED_CLOCK,
            updated_by="test",
        ),
    )


def test_sqlite_create_get_roundtrip(tmp_path) -> None:
    db = tmp_path / "t.db"
    clock_calls: list[datetime] = []

    def clk() -> datetime:
        t = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
        clock_calls.append(t)
        return t

    store = SQLiteStateStore(str(db), config=InMemoryStateStoreConfig(clock=clk))
    sid = uuid4()
    cid = uuid4()
    snap = _minimal_state(state_id=sid, candidate_id=cid)
    cr = store.create(snap)
    assert cr.ok and cr.meta is not None
    assert cr.meta.store_revision == 1
    g = store.get(sid)
    assert g.ok and g.snapshot is not None
    if hasattr(g.snapshot, "model_dump"):
        assert g.snapshot.model_dump() == snap.model_dump()
    store.close()


def test_replace_increments_revision_and_revision_mismatch(tmp_path) -> None:
    db = tmp_path / "t.db"
    store = SQLiteStateStore(
        str(db),
        config=InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK),
    )
    sid = uuid4()
    cid = uuid4()
    assert store.create(_minimal_state(state_id=sid, candidate_id=cid)).ok
    snap2 = _minimal_state(state_id=sid, candidate_id=cid, phase=PipelinePhase.CV_RECEIVED)
    bad = store.replace(sid, snap2, expected_store_revision=99)
    assert not bad.ok and bad.failure and bad.failure.code == StateStoreFailureCode.REVISION_MISMATCH
    ok = store.replace(sid, snap2, expected_store_revision=1)
    assert ok.ok and ok.meta and ok.meta.store_revision == 2
    store.close()


def test_get_for_candidate(tmp_path) -> None:
    db = tmp_path / "t.db"
    store = SQLiteStateStore(str(db), config=InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK))
    sid = uuid4()
    cid = uuid4()
    store.create(_minimal_state(state_id=sid, candidate_id=cid))
    gc = store.get_for_candidate(cid)
    assert gc.ok and gc.snapshot and gc.snapshot.id == sid
    store.close()


def test_restart_new_connection_same_db(tmp_path) -> None:
    db = tmp_path / "t.db"
    sid = uuid4()
    cid = uuid4()
    snap = _minimal_state(state_id=sid, candidate_id=cid)

    s1 = SQLiteStateStore(str(db), config=InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK))
    assert s1.create(snap).ok
    s1.close()

    s2 = SQLiteStateStore(str(db), config=InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK))
    got = s2.get(sid)
    assert got.ok and got.snapshot and got.snapshot.pipeline.phase == PipelinePhase.NEW
    assert got.meta and got.meta.store_revision == 1
    s2.close()


def test_multi_candidate_isolation(tmp_path) -> None:
    db = tmp_path / "t.db"
    store = SQLiteStateStore(str(db), config=InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK))
    s1 = uuid4()
    c1 = uuid4()
    s2 = uuid4()
    c2 = uuid4()
    store.create(_minimal_state(state_id=s1, candidate_id=c1))
    store.create(_minimal_state(state_id=s2, candidate_id=c2, phase=PipelinePhase.CV_RECEIVED))
    g1 = store.get_for_candidate(c1)
    g2 = store.get_for_candidate(c2)
    assert g1.snapshot.id == s1
    assert g2.snapshot.id == s2
    assert g1.snapshot.pipeline.phase == PipelinePhase.NEW
    assert g2.snapshot.pipeline.phase == PipelinePhase.CV_RECEIVED
    store.close()


def test_audit_row_count_matches_transitions(tmp_path) -> None:
    db = tmp_path / "t.db"
    store = SQLiteStateStore(str(db), config=InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK))
    sid = uuid4()
    cid = uuid4()
    snap = _minimal_state(state_id=sid, candidate_id=cid)
    assert len(snap.transitions) == 0
    store.create(snap)
    assert store.audit_transition_count(sid) == 0
    from schemas.state_schema import DecisionActorType, StateActor, StateDomain, StateTransitionRecord

    tr = StateTransitionRecord(
        state_domain=StateDomain.PIPELINE,
        from_state=PipelinePhase.NEW.value,
        to_state=PipelinePhase.CV_RECEIVED.value,
        trigger="event:test",
        timestamp=_FIXED_CLOCK,
        actor=StateActor(actor_type=DecisionActorType.SYSTEM, actor_id="sys"),
    )
    snap2 = snap.model_copy(deep=True, update={"transitions": [tr]})
    store.replace(sid, snap2, expected_store_revision=1)
    assert store.audit_transition_count(sid) == 1
    store.close()


def test_capacity_limit(tmp_path) -> None:
    db = tmp_path / "t.db"
    cfg = InMemoryStateStoreConfig(
        clock=lambda: _FIXED_CLOCK,
        limits=InMemoryStateStoreLimits(max_distinct_states=1),
    )
    store = SQLiteStateStore(str(db), config=cfg)
    store.create(_minimal_state(state_id=uuid4(), candidate_id=uuid4()))
    r2 = store.create(_minimal_state(state_id=uuid4(), candidate_id=uuid4()))
    assert not r2.ok and r2.failure and r2.failure.code == StateStoreFailureCode.CAPACITY_EXCEEDED
    store.close()


def test_wire_vertical_slice_sqlite_survives_reload(tmp_path) -> None:
    db = tmp_path / "slice.db"
    cfg = InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK)
    store = SQLiteStateStore(str(db), config=cfg)
    bundle = wire_vertical_slice_runtime(bus=RecordingInMemoryEventBus(), store=store)
    drive_vertical_slice_primary_sequence(bundle)
    sid = bundle.state_id
    store.close()

    store2 = SQLiteStateStore(str(db), config=cfg)
    fin = store2.get(sid)
    assert fin.ok and fin.snapshot is not None
    assert fin.snapshot.pipeline.phase == PipelinePhase.DEEP_SCORED
    store2.close()


def test_wire_vertical_slice_sqlite_second_process_reuses_row(tmp_path) -> None:
    """Same DB + deterministic ids: second wire must not fail on ALREADY_EXISTS."""
    db = tmp_path / "restart.db"
    cfg = InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK)
    store1 = SQLiteStateStore(str(db), config=cfg)
    b1 = wire_vertical_slice_runtime(bus=RecordingInMemoryEventBus(), store=store1)
    sid = b1.state_id
    store1.close()

    store2 = SQLiteStateStore(str(db), config=cfg)
    b2 = wire_vertical_slice_runtime(bus=RecordingInMemoryEventBus(), store=store2)
    assert b2.state_id == sid
    got = store2.get(sid)
    assert got.ok and got.snapshot is not None
    assert got.snapshot.pipeline.phase == PipelinePhase.NEW
    store2.close()


def test_sqlite_full_pipeline_decision_extensions_survive_reload(tmp_path) -> None:
    """Decision keys in ``OrchestrationState.extensions`` round-trip through SQLite."""
    db = tmp_path / "decisions.db"
    cfg = InMemoryStateStoreConfig(clock=lambda: _FIXED_CLOCK)
    store = SQLiteStateStore(str(db), config=cfg)
    bundle = wire_vertical_slice_runtime(bus=RecordingInMemoryEventBus(), store=store)
    drive_vertical_slice_primary_sequence(bundle)
    sid = bundle.state_id
    fin = store.get(sid)
    assert fin.ok and fin.snapshot is not None
    ex = fin.snapshot.extensions
    assert ex.get("decision.hard_filter_pass") is True
    assert ex.get("decision.light_score") is not None
    assert ex.get("decision.deep_score") is not None
    assert isinstance(ex.get("decision.evidence_refs"), list)
    store.close()

    store2 = SQLiteStateStore(str(db), config=cfg)
    reloaded = store2.get(sid)
    assert reloaded.ok and reloaded.snapshot is not None
    ex2 = reloaded.snapshot.extensions
    assert ex2.get("decision.light_score") is not None
    assert ex2.get("decision.deep_score") is not None
    store2.close()
