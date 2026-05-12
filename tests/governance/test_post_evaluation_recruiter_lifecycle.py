"""
Post-``deep_scored`` recruiter governance: hire ladder, rejects, invalid/duplicate NOOPs, replay parity.
"""

from __future__ import annotations

from typing import Any, Dict
from uuid import uuid5

from interfaces.event_bus_interface import EventEnvelope, EventEnvelopeMetadata
from orchestrator.orchestrator import OrchestrationDecisionKind
from runtime.bootstrap_vertical_slice import (
    _BOOT_NS,
    _FIXED_CLOCK,
    drive_vertical_slice_primary_sequence,
    vertical_slice_timeline_text,
    wire_vertical_slice_runtime,
)
from schemas.state_schema import PipelinePhase

from tests.governance.test_vertical_slice_governance import _GOV_BASE, _json_dict
from tests.replay.recording_bus import RecordingInMemoryEventBus


def _gov_envelope(
    *,
    event_type: str,
    seq: int,
    candidate_id,
    correlation_id,
    payload: Dict[str, Any],
) -> EventEnvelope:
    eid = uuid5(_BOOT_NS, f"gov:{event_type}:{seq}")
    return EventEnvelope(
        event_id=eid,
        event_type=event_type,
        occurred_at=_FIXED_CLOCK,
        subject_id=candidate_id,
        subject_kind="candidate",
        payload=payload,
        metadata=EventEnvelopeMetadata(
            correlation_id=correlation_id,
            causation_id=None,
            actor_id=str(payload.get("actor_id", "")),
        ),
    )


def _publish(bundle: Any, event_type: str, seq: int) -> None:
    env = _gov_envelope(
        event_type=event_type,
        seq=seq,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=dict(_GOV_BASE),
    )
    assert bundle.bus.publish(env).status.value == "accepted"


def test_hire_ladder_governance_through_hired() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 200
    for et in (
        "recruiter_approve_candidate",
        "recruiter_schedule_interview",
        "recruiter_complete_interview",
        "recruiter_send_offer",
        "recruiter_mark_hired",
    ):
        _publish(bundle, et, seq)
        seq += 1
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.HIRED
    codes = [(tr.extensions or {}).get("governance.decision_code") for tr in snap.transitions]
    assert "GOVERNANCE_APPROVE_CANDIDATE" in codes
    assert "GOVERNANCE_SCHEDULE_INTERVIEW" in codes
    assert "GOVERNANCE_COMPLETE_INTERVIEW" in codes
    assert "GOVERNANCE_SEND_OFFER" in codes
    assert "GOVERNANCE_MARK_HIRED" in codes


def test_reject_from_shortlisted_to_inactive() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    _publish(bundle, "recruiter_approve_candidate", 210)
    _publish(bundle, "recruiter_reject_candidate", 211)
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.INACTIVE


def test_invalid_schedule_from_deep_scored_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    phase_before = bundle.store.get(bundle.state_id).snapshot.pipeline.phase
    assert phase_before == PipelinePhase.DEEP_SCORED
    _publish(bundle, "recruiter_schedule_interview", 220)
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap.pipeline.phase == PipelinePhase.DEEP_SCORED
    last = bundle.subscriber.run_history[-1]
    assert last.ok
    assert any(d.kind == OrchestrationDecisionKind.NOOP for d in last.decisions)


def test_duplicate_approve_after_shortlisted_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    _publish(bundle, "recruiter_approve_candidate", 230)
    _publish(bundle, "recruiter_approve_candidate", 231)
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap.pipeline.phase == PipelinePhase.SHORTLISTED
    last = bundle.subscriber.run_history[-1]
    assert any(d.kind == OrchestrationDecisionKind.NOOP for d in last.decisions)


def test_duplicate_schedule_interview_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    _publish(bundle, "recruiter_approve_candidate", 240)
    _publish(bundle, "recruiter_schedule_interview", 241)
    _publish(bundle, "recruiter_schedule_interview", 242)
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap.pipeline.phase == PipelinePhase.INTERVIEW_PENDING
    last = bundle.subscriber.run_history[-1]
    assert any(d.kind == OrchestrationDecisionKind.NOOP for d in last.decisions)


def test_reject_from_hired_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 250
    for et in (
        "recruiter_approve_candidate",
        "recruiter_schedule_interview",
        "recruiter_complete_interview",
        "recruiter_send_offer",
        "recruiter_mark_hired",
    ):
        _publish(bundle, et, seq)
        seq += 1
    _publish(bundle, "recruiter_reject_candidate", 260)
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap.pipeline.phase == PipelinePhase.HIRED


def test_governance_hire_ladder_replay_parity() -> None:
    def drive_hire(bus: RecordingInMemoryEventBus) -> Any:
        bundle = wire_vertical_slice_runtime(bus=bus)
        drive_vertical_slice_primary_sequence(bundle)
        seq = 300
        for et in (
            "recruiter_approve_candidate",
            "recruiter_schedule_interview",
            "recruiter_complete_interview",
            "recruiter_send_offer",
            "recruiter_mark_hired",
        ):
            _publish(bundle, et, seq)
            seq += 1
        return bundle

    b1 = RecordingInMemoryEventBus()
    b2 = RecordingInMemoryEventBus()
    x1 = drive_hire(b1)
    x2 = drive_hire(b2)
    s1 = x1.store.get(x1.state_id).snapshot
    s2 = x2.store.get(x2.state_id).snapshot
    assert s1 is not None and s2 is not None
    assert _json_dict(s1) == _json_dict(s2)
    assert vertical_slice_timeline_text(x1) == vertical_slice_timeline_text(x2)
