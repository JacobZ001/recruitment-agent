"""
Negative-path deterministic replay checks for the recruiter vertical slice.

Complements ``test_vertical_slice_replay.py`` (happy path): failures must be as
stable and inspectable as successes for Phase 3 workflow validation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from interfaces.event_bus_interface import (
    DeliveryStatus,
    EventEnvelope,
    EventBusFailure,
    HandleResult,
    SubscriptionSelector,
    SubscriptionSpec,
)
from orchestrator.orchestrator import (
    OrchestrationFailureCode,
    OrchestrationPlan,
    ProposedTransition,
)
from orchestrator.vertical_slice_planner import (
    SKILL_LIGHT_SCORING,
    VerticalSlicePlanner,
)
from runtime.bootstrap_vertical_slice import (
    VerticalSliceRuntimeBundle,
    _FIXED_CLOCK,
    _envelope,
    _skill_registry,
    wire_vertical_slice_runtime,
)
from runtime.in_memory_event_bus import HANDLER_EXCEPTION_CODE, SimpleEventSubscription
from schemas.state_schema import DecisionActorType, PipelinePhase, StateActor, StateDomain

from tests.replay.recording_bus import RecordingInMemoryEventBus


def _json_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    raise TypeError(f"unsupported model type: {type(model)!r}")


def _publish(
    bundle: VerticalSliceRuntimeBundle,
    event_types: Tuple[str, ...],
    *,
    seq_start: int = 1,
) -> None:
    """Publish ingress envelopes in order; expects each publish ACCEPTED."""
    clock = _FIXED_CLOCK
    candidate_id = bundle.candidate_id
    correlation_id = bundle.correlation_id
    for i, et in enumerate(event_types):
        env = _envelope(
            event_type=et,
            candidate_id=candidate_id,
            correlation_id=correlation_id,
            occurred_at=clock,
            seq=seq_start + i,
        )
        pr = bundle.bus.publish(env)
        assert pr.status == DeliveryStatus.ACCEPTED, (et, pr.status, pr.failure)


def _publish_one_expect_rejected(bundle: VerticalSliceRuntimeBundle, event_type: str, *, seq: int) -> None:
    """Single ingress publish where the orchestrator rejects (bus aggregate REJECTED)."""
    env = _envelope(
        event_type=event_type,
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        occurred_at=_FIXED_CLOCK,
        seq=seq,
    )
    pr = bundle.bus.publish(env)
    assert pr.status == DeliveryStatus.REJECTED
    assert pr.failure is not None
    assert isinstance(pr.failure, EventBusFailure)


EVENTS_TO_CV_PARSED: Tuple[str, ...] = (
    "candidate_created",
    "cv_uploaded",
    "cv_parsed",
)


class InvalidHardFilterPassedPlanner(VerticalSlicePlanner):
    """
    Emits an illegal pipeline edge (cv_parsed -> light_scored) so the transition
    engine rejects the proposal deterministically.
    """

    def plan(self, *, state, envelope, delivery):  # type: ignore[no-untyped-def]
        if (
            envelope.event_type == "hard_filter_passed"
            and state.pipeline.phase == PipelinePhase.CV_PARSED
        ):
            actor_id = envelope.metadata.actor_id if envelope.metadata else None
            return OrchestrationPlan(
                proposed_transition=ProposedTransition(
                    state_domain=StateDomain.PIPELINE,
                    from_state=PipelinePhase.CV_PARSED.value,
                    to_state=PipelinePhase.LIGHT_SCORED.value,
                    trigger="event:hard_filter_passed",
                    human_override=False,
                    transition_actor=StateActor(actor_type=DecisionActorType.SYSTEM, actor_id=actor_id),
                ),
                skills=(),
            )
        return super().plan(state=state, envelope=envelope, delivery=delivery)


class RaisingProbe:
    """Deterministic exception for bus boundary isolation tests."""

    def handle(self, envelope: EventEnvelope, context: Any) -> HandleResult:  # noqa: ARG002
        raise RuntimeError("deterministic_bus_handler_probe")


def test_hard_filter_failed_path_replay_twice_identical() -> None:
    """``hard_filter_failed`` closes the slice to ``inactive`` with stable artifacts."""
    seq = ("candidate_created", "cv_uploaded", "cv_parsed", "hard_filter_failed")

    bus_a = RecordingInMemoryEventBus()
    bus_b = RecordingInMemoryEventBus()

    bundle_a = wire_vertical_slice_runtime(bus=bus_a)
    bundle_b = wire_vertical_slice_runtime(bus=bus_b)
    _publish(bundle_a, seq)
    _publish(bundle_b, seq)

    fin_a = bundle_a.store.get(bundle_a.state_id).snapshot
    fin_b = bundle_b.store.get(bundle_b.state_id).snapshot
    assert fin_a is not None and fin_b is not None
    assert fin_a.pipeline.phase == PipelinePhase.INACTIVE
    assert len(fin_a.transitions) == 3

    assert _json_dict(fin_a) == _json_dict(fin_b)
    assert _runs_json(bundle_a.subscriber.run_history) == _runs_json(bundle_b.subscriber.run_history)
    assert len(bundle_a.subscriber.run_history) == 4


def test_invalid_transition_rejected_state_unchanged() -> None:
    """Illegal ``from_state``/``to_state`` pair fails validation; aggregate does not advance."""
    bundle = wire_vertical_slice_runtime(planner=InvalidHardFilterPassedPlanner())
    _publish(bundle, EVENTS_TO_CV_PARSED)

    before = bundle.store.get(bundle.state_id).snapshot
    assert before is not None
    assert before.pipeline.phase == PipelinePhase.CV_PARSED

    _publish_one_expect_rejected(bundle, "hard_filter_passed", seq=4)

    after = bundle.store.get(bundle.state_id).snapshot
    assert after is not None
    assert after.pipeline.phase == PipelinePhase.CV_PARSED
    assert _json_dict(after) == _json_dict(before)

    last = bundle.subscriber.last_run
    assert last is not None and not last.ok and last.failure is not None
    assert last.failure.code == OrchestrationFailureCode.TRANSITION_REJECTED


def test_missing_required_skill_not_registered() -> None:
    """Planner requests light scoring but orchestrator rejects when skill is absent from registry."""
    reg = dict(_skill_registry())
    del reg[SKILL_LIGHT_SCORING]
    bundle = wire_vertical_slice_runtime(skills=reg)

    _publish(
        bundle,
        (
            "candidate_created",
            "cv_uploaded",
            "cv_parsed",
            "hard_filter_passed",
        ),
    )
    _publish_one_expect_rejected(bundle, "light_scoring_completed", seq=5)

    snap = bundle.store.get(bundle.state_id).snapshot
    assert snap is not None
    assert snap.pipeline.phase == PipelinePhase.HARD_FILTER_PASSED

    last = bundle.subscriber.last_run
    assert last is not None and not last.ok and last.failure is not None
    assert last.failure.code == OrchestrationFailureCode.SKILL_NOT_REGISTERED
    details = last.failure.details or {}
    assert details.get("skill_name") == SKILL_LIGHT_SCORING


def test_bus_handler_exception_failed_publish_result_twice_identical() -> None:
    """Handler ``Exception`` maps to structured failed ``HandleResult``; aggregate publish fails."""
    bundle = wire_vertical_slice_runtime()
    bus = bundle.bus

    bus.register_subscription(
        SimpleEventSubscription(
            spec=SubscriptionSpec(
                subscriber_id="replay.probe.raise",
                subscription_id="000.probe.raise",
                selector=SubscriptionSelector(
                    subject_kind="candidate",
                    event_types=["bus_handler_exception_probe"],
                ),
            ),
            handler=RaisingProbe(),
        )
    )

    env = _envelope(
        event_type="bus_handler_exception_probe",
        candidate_id=bundle.candidate_id,
        correlation_id=bundle.correlation_id,
        occurred_at=_FIXED_CLOCK,
        seq=1,
    )

    pr_a = bus.publish(env)
    pr_b = bus.publish(env)

    assert pr_a.status == DeliveryStatus.FAILED
    assert pr_b.status == DeliveryStatus.FAILED
    assert pr_a.failure is not None and pr_b.failure is not None

    dump_a = _json_dict(pr_a)
    dump_b = _json_dict(pr_b)
    assert dump_a == dump_b

    trace = dump_a["extensions"]["dispatch_trace"]
    dispatch = trace["dispatch_records"]
    assert len(dispatch) == 2
    probe_row = next(r for r in dispatch if r["subscription_id"] == "000.probe.raise")
    orch_row = next(r for r in dispatch if r["subscription_id"] == "bootstrap.vertical_slice.orchestrator")
    assert probe_row["dispatched"] is True
    hr = probe_row["handle_result"]
    assert hr["status"] == "failed"
    assert hr["failure"]["code"] == HANDLER_EXCEPTION_CODE
    assert hr["failure"]["extensions"]["exception_type"] == "RuntimeError"
    assert orch_row["dispatched"] is True


def _runs_json(runs: List[Any]) -> List[Dict[str, Any]]:
    return [_json_dict(r) for r in runs]
