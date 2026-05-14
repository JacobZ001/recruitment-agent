"""Business workflow semantics: ranking branches, offers, reconsider, interview loop."""

from __future__ import annotations

from interfaces.event_bus_interface import EventEnvelope

from orchestrator.orchestrator import OrchestrationDecisionKind
from runtime.bootstrap_vertical_slice import (
    _FIXED_CLOCK,
    _envelope,
    drive_vertical_slice_primary_sequence,
    wire_vertical_slice_runtime,
)
from schemas.state_schema import PipelinePhase

from tests.governance.test_vertical_slice_governance import _GOV_BASE, _gov_envelope
from tests.replay.recording_bus import RecordingInMemoryEventBus
from tests.replay.test_vertical_slice_negative_paths import _publish as publish_tuple


def _light_env(bundle, *, seq: int, ranking_branch: str) -> EventEnvelope:
    base = _envelope(
        event_type="light_scoring_completed",
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        occurred_at=_FIXED_CLOCK,
        seq=seq,
    )
    pl = dict(base.payload)
    pl["ranking.branch"] = ranking_branch
    return base.model_copy(update={"payload": pl})


def test_questionnaire_path_to_shortlist() -> None:
    """Default light ranking mid_m → questionnaire leg → deep ranking top_k → shortlisted."""
    from runtime.bootstrap_vertical_slice import PRIMARY_VERTICAL_SLICE_EVENT_TYPES

    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    publish_tuple(bundle, tuple(PRIMARY_VERTICAL_SLICE_EVENT_TYPES))
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.SHORTLISTED


def test_light_ranking_top_k_skips_questionnaire_to_shortlisted() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    publish_tuple(
        bundle,
        ("candidate_created", "cv_uploaded", "cv_parsed", "hard_filter_passed"),
    )
    assert bundle.bus.publish(_light_env(bundle, seq=5, ranking_branch="top_k")).status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.SHORTLISTED


def test_light_ranking_reject_inactive_reason_persisted() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    publish_tuple(
        bundle,
        ("candidate_created", "cv_uploaded", "cv_parsed", "hard_filter_passed"),
    )
    assert bundle.bus.publish(_light_env(bundle, seq=5, ranking_branch="reject")).status.value == "accepted"
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.INACTIVE
    assert snap.extensions.get("inactive.reason") == "ranking_reject_after_light_scoring"


def test_duplicate_send_offer_from_offer_sent_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 400
    for et in ("recruiter_schedule_interview", "recruiter_complete_interview", "recruiter_send_offer"):
        pr = bundle.bus.publish(
            _gov_envelope(
                event_type=et,
                seq=seq,
                candidate_id=bundle.candidate_id,
                correlation_id=bundle.correlation_id,
                payload=dict(_GOV_BASE),
            )
        )
        assert pr.status.value == "accepted"
        seq += 1
    assert bundle.store.get(bundle.state_id).snapshot.pipeline.phase == PipelinePhase.OFFER_SENT
    pr2 = bundle.bus.publish(
        _gov_envelope(
            event_type="recruiter_send_offer",
            seq=seq,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
    )
    assert pr2.status.value == "accepted"
    last = bundle.subscriber.run_history[-1]
    assert last.ok
    assert any(d.kind == OrchestrationDecisionKind.NOOP for d in last.decisions)


def test_candidate_decline_offer_sets_inactive_reason() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 500
    for et in ("recruiter_schedule_interview", "recruiter_complete_interview", "recruiter_send_offer"):
        bundle.bus.publish(
            _gov_envelope(
                event_type=et,
                seq=seq,
                candidate_id=bundle.candidate_id,
                correlation_id=bundle.correlation_id,
                payload=dict(_GOV_BASE),
            )
        )
        seq += 1
    bundle.bus.publish(
        _gov_envelope(
            event_type="candidate_decline_offer",
            seq=seq,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
    )
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap.pipeline.phase == PipelinePhase.INACTIVE
    assert snap.extensions.get("inactive.reason") == "offer_declined"


def test_inactive_reconsider_returns_shortlisted() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 600
    bundle.bus.publish(
        _gov_envelope(
            event_type="recruiter_reject_candidate",
            seq=seq,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
    )
    seq += 1
    assert bundle.store.get(bundle.state_id).snapshot.pipeline.phase == PipelinePhase.INACTIVE
    bundle.bus.publish(
        _gov_envelope(
            event_type="recruiter_reconsider_candidate",
            seq=seq,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
    )
    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap.pipeline.phase == PipelinePhase.SHORTLISTED
    assert snap.extensions.get("inactive.reason") in (None, "")


def test_interview_completed_schedule_interview_next_round() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 700
    for et in ("recruiter_schedule_interview", "recruiter_complete_interview"):
        bundle.bus.publish(
            _gov_envelope(
                event_type=et,
                seq=seq,
                candidate_id=bundle.candidate_id,
                correlation_id=bundle.correlation_id,
                payload=dict(_GOV_BASE),
            )
        )
        seq += 1
    assert bundle.store.get(bundle.state_id).snapshot.pipeline.phase == PipelinePhase.INTERVIEW_COMPLETED
    bundle.bus.publish(
        _gov_envelope(
            event_type="recruiter_schedule_interview",
            seq=seq,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
    )
    assert bundle.store.get(bundle.state_id).snapshot.pipeline.phase == PipelinePhase.INTERVIEW_PENDING


def test_recruiter_action_from_hired_is_noop() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle)
    seq = 800
    for et in (
        "recruiter_schedule_interview",
        "recruiter_complete_interview",
        "recruiter_send_offer",
        "candidate_accept_offer",
    ):
        bundle.bus.publish(
            _gov_envelope(
                event_type=et,
                seq=seq,
                candidate_id=bundle.candidate_id,
                correlation_id=bundle.correlation_id,
                payload=dict(_GOV_BASE),
            )
        )
        seq += 1
    assert bundle.store.get(bundle.state_id).snapshot.pipeline.phase == PipelinePhase.HIRED
    bundle.bus.publish(
        _gov_envelope(
            event_type="recruiter_send_offer",
            seq=seq,
            candidate_id=bundle.candidate_id,
            correlation_id=bundle.correlation_id,
            payload=dict(_GOV_BASE),
        )
    )
    last = bundle.subscriber.run_history[-1]
    assert any(d.kind == OrchestrationDecisionKind.NOOP for d in last.decisions)
