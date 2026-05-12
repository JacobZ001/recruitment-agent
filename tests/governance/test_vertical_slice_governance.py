"""
Deterministic human-governance ingress for the vertical slice (replay-safe; no auth/DB).
"""

from __future__ import annotations

from typing import Any, Dict, List

from uuid import uuid5

from interfaces.event_bus_interface import EventEnvelope, EventEnvelopeMetadata
from orchestrator.orchestrator import OrchestrationExecutionResult, OrchestrationFailureCode
from runtime.bootstrap_vertical_slice import (
    _BOOT_NS,
    _FIXED_CLOCK,
    drive_vertical_slice_primary_sequence,
    vertical_slice_primary_ingress_envelopes,
    vertical_slice_timeline_text,
    wire_vertical_slice_runtime,
)
from schemas.state_schema import PipelinePhase

from tests.replay.recording_bus import RecordingInMemoryEventBus


def _json_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    raise TypeError(f"unsupported model type: {type(model)!r}")


def _runs_payload(runs: List[OrchestrationExecutionResult]) -> List[Dict[str, Any]]:
    return [_json_dict(r) for r in runs]


_GOV_BASE: Dict[str, Any] = {
    "actor_id": "recruiter:alice",
    "actor_type": "recruiter",
    "reason": "Structured governance reason",
    "evidence_refs": ["artifact://review/2026-05-12/1"],
}


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


def test_governance_approve_candidate_advances_to_shortlisted() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    env = _gov_envelope(
        event_type="recruiter_approve_candidate",
        seq=50,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=dict(_GOV_BASE),
    )
    pr = bus.publish(env)
    assert pr.status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.SHORTLISTED
    codes = [(tr.extensions or {}).get("governance.decision_code") for tr in snap.transitions]
    assert "GOVERNANCE_APPROVE_CANDIDATE" in codes


def test_governance_reject_candidate_to_inactive() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    env = _gov_envelope(
        event_type="recruiter_reject_candidate",
        seq=51,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=dict(_GOV_BASE),
    )
    pr = bus.publish(env)
    assert pr.status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.INACTIVE
    codes = [(tr.extensions or {}).get("governance.decision_code") for tr in snap.transitions]
    assert "GOVERNANCE_REJECT_CANDIDATE" in codes


def test_governance_override_transition_shortlisted_to_interview_pending() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    env_appr = _gov_envelope(
        event_type="recruiter_approve_candidate",
        seq=52,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=dict(_GOV_BASE),
    )
    assert bus.publish(env_appr).status.value == "accepted"
    payload = {
        **_GOV_BASE,
        "requested_from_phase": PipelinePhase.SHORTLISTED.value,
        "requested_to_phase": PipelinePhase.INTERVIEW_PENDING.value,
        "trigger": "manual_recruiter_schedule_interview",
        "force_human_override": False,
    }
    env_ov = _gov_envelope(
        event_type="recruiter_override_transition",
        seq=53,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=payload,
    )
    assert bus.publish(env_ov).status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.INTERVIEW_PENDING


def test_governance_state_mismatch_on_override_wrong_current_phase() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    # Stop after hard_filter_passed so phase stays HARD_FILTER_PASSED (no questionnaire leg yet).
    for env in vertical_slice_primary_ingress_envelopes(bundle):
        bundle.bus.publish(env)
        if env.event_type == "hard_filter_passed":
            break
    payload = {
        **_GOV_BASE,
        "requested_from_phase": PipelinePhase.DEEP_SCORED.value,
        "requested_to_phase": PipelinePhase.SHORTLISTED.value,
        "trigger": "manual_recruiter_approve",
    }
    env_bad = _gov_envelope(
        event_type="recruiter_override_transition",
        seq=60,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=payload,
    )
    pr = bundle.bus.publish(env_bad)
    assert pr.status.value != "accepted"
    failed_runs = [r for r in bundle.subscriber.run_history if not r.ok]
    assert failed_runs
    last_fail = failed_runs[-1]
    assert last_fail.failure is not None
    assert last_fail.failure.code == OrchestrationFailureCode.STATE_MISMATCH


def test_governance_invalid_payload_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    env = _gov_envelope(
        event_type="recruiter_approve_candidate",
        seq=61,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload={},  # missing required governance fields
    )
    pr = bus.publish(env)
    assert pr.status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.DEEP_SCORED


def test_governance_timeline_contains_audit_lines() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    env = _gov_envelope(
        event_type="recruiter_approve_candidate",
        seq=62,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=dict(_GOV_BASE),
    )
    bundle.bus.publish(env)
    text = vertical_slice_timeline_text(bundle)
    assert "governance.ingress" in text
    assert "governance.transition" in text
    assert "GOVERNANCE_APPROVE_CANDIDATE" in text


def test_governance_replay_twice_identical() -> None:
    bus_a = RecordingInMemoryEventBus()
    bus_b = RecordingInMemoryEventBus()

    def drive(bundle: Any) -> None:
        drive_vertical_slice_primary_sequence(bundle)
        env = _gov_envelope(
            event_type="recruiter_approve_candidate",
            seq=70,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
        bundle.bus.publish(env)

    bundle_a = wire_vertical_slice_runtime(bus=bus_a)
    bundle_b = wire_vertical_slice_runtime(bus=bus_b)
    drive(bundle_a)
    drive(bundle_b)

    fa = bundle_a.store.get(bundle_a.state_id).snapshot
    fb = bundle_b.store.get(bundle_b.state_id).snapshot
    assert fa is not None and fb is not None
    assert _json_dict(fa) == _json_dict(fb)
    assert _runs_payload(bundle_a.subscriber.run_history) == _runs_payload(bundle_b.subscriber.run_history)


def test_governance_force_transition_sets_human_override_flag() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    payload = {
        **_GOV_BASE,
        "requested_from_phase": PipelinePhase.DEEP_SCORED.value,
        "requested_to_phase": PipelinePhase.SHORTLISTED.value,
        "trigger": "manual_recruiter_approve",
    }
    env = _gov_envelope(
        event_type="recruiter_force_transition",
        seq=80,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        payload=payload,
    )
    assert bus.publish(env).status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.SHORTLISTED
    last_tr = snap.transitions[-1]
    assert (last_tr.extensions or {}).get("governance.force_human_override") is True
