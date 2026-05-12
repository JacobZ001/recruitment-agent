"""Deterministic decision/evidence summaries and operator navigation (inspection-only)."""

from __future__ import annotations

from uuid import uuid4

from interfaces.skill_interface import (
    EvidenceKind,
    EvidenceRef,
    ExecutionAudit,
    ExecutionStatus,
    ExecutionTiming,
    SkillExecutionResult,
    SkillMetadata,
    SkillOutputEnvelope,
)
from orchestrator.orchestrator import OrchestrationExecutionResult, OrchestrationTraceMeta
from runtime.bootstrap_vertical_slice import (
    drive_vertical_slice_primary_sequence,
    resolve_vertical_slice_inspection_catalog,
    wire_vertical_slice_runtime,
)
from runtime.inspection.decision_evidence import (
    build_vertical_slice_operator_navigation,
    render_operator_navigation_text,
    skill_decision_summary_parts,
    skill_decision_timeline_lines,
    transition_trail_rows,
    truncate_for_inspection,
)
from runtime.inspection.timeline import render_vertical_slice_timeline_text
from schemas.state_schema import (
    DecisionActorType,
    OrchestrationState,
    PipelinePhase,
    PipelineState,
    PipelineStatus,
    StateActor,
    StateAudit,
    StateDomain,
    StateTransitionRecord,
)

from skills.deterministic.fake_hard_filter_skill import FakeHardFilterSkill
from skills.deterministic.fake_light_scoring_skill import FakeLightScoringSkill

from tests.replay.recording_bus import RecordingInMemoryEventBus


def _filter_meta() -> SkillMetadata:
    return FakeHardFilterSkill().metadata


def _light_meta() -> SkillMetadata:
    return FakeLightScoringSkill().metadata


def test_truncate_for_inspection_deterministic() -> None:
    assert truncate_for_inspection("short") == "short"
    long = "x" * 250
    out = truncate_for_inspection(long, max_chars=50)
    assert len(out) == 50
    assert out.endswith("...")


def test_skill_decision_summary_filter_shape() -> None:
    sr = SkillExecutionResult(
        metadata=_filter_meta(),
        status=ExecutionStatus.SUCCEEDED,
        output=SkillOutputEnvelope(
            payload={
                "filter.decision": "passed",
                "filter.computed_pass": True,
                "filter.rejection.reason_codes": ["missing_field:x", "other:y"],
            }
        ),
        timing=ExecutionTiming(),
        audit=ExecutionAudit(execution_id=uuid4()),
    )
    p = skill_decision_summary_parts(sr)
    assert "decision.summary" in p
    assert "filter.reason_codes" in p
    assert "missing_field:x" in p["filter.reason_codes"]


def test_skill_decision_timeline_lines_include_score_summary() -> None:
    sr = SkillExecutionResult(
        metadata=_light_meta(),
        status=ExecutionStatus.SUCCEEDED,
        output=SkillOutputEnvelope(
            payload={
                "scoring.kind": "light",
                "scoring.normalized_score": 0.42,
                "scoring.signal_codes": ["a", "b"],
            },
            evidence_refs=[
                EvidenceRef(kind=EvidenceKind.METRIC, ref="metric://x"),
            ],
        ),
        timing=ExecutionTiming(),
        audit=ExecutionAudit(execution_id=uuid4()),
    )
    lines = skill_decision_timeline_lines(sr)
    assert any("score.summary=" in ln for ln in lines)
    assert any("evidence.refs=" in ln for ln in lines)


def test_transition_trail_rows_include_governance_codes() -> None:
    tr = StateTransitionRecord(
        state_domain=StateDomain.PIPELINE,
        from_state="deep_scored",
        to_state="shortlisted",
        trigger="manual_recruiter_approve",
        actor=StateActor(actor_type=DecisionActorType.HUMAN, actor_id="r:a"),
        extensions={
            "matched_rule_id": "pipeline.deep_scored_to_shortlisted",
            "governance.decision_code": "GOVERNANCE_APPROVE_CANDIDATE",
            "governance.reason": "fit",
            "governance.evidence_refs": ["artifact://1"],
        },
    )
    st = OrchestrationState(
        id=uuid4(),
        pipeline=PipelineState(phase=PipelinePhase.SHORTLISTED, status=PipelineStatus.ACTIVE),
        audit=StateAudit(),
        transitions=(tr,),
    )
    rows = transition_trail_rows(st)
    assert rows[-1]["governance.decision_code"] == "GOVERNANCE_APPROVE_CANDIDATE"
    assert rows[-1]["governance.evidence_refs"] == ["artifact://1"]


def test_operator_navigation_replay_stable_dict() -> None:
    """Two synthetic histories with identical facts produce identical navigation dicts."""
    tr = StateTransitionRecord(
        state_domain=StateDomain.PIPELINE,
        from_state="new",
        to_state="cv_received",
        trigger="event:cv_uploaded",
        actor=StateActor(actor_type=DecisionActorType.SYSTEM, actor_id="sys"),
        extensions={"matched_rule_id": "pipeline.new_to_cv_received"},
    )
    st = OrchestrationState(
        id=uuid4(),
        pipeline=PipelineState(phase=PipelinePhase.CV_RECEIVED, status=PipelineStatus.ACTIVE),
        audit=StateAudit(),
        transitions=(tr,),
    )
    trace = OrchestrationTraceMeta(orchestration_execution_id=uuid4(), ingested_event_id=uuid4())
    run = OrchestrationExecutionResult(
        ok=True,
        new_state=st,
        trace=trace,
        decisions=(),
    )
    nav_a = build_vertical_slice_operator_navigation(
        final_state=st, run_history=(run,), envelope_catalog=()
    )
    nav_b = build_vertical_slice_operator_navigation(
        final_state=st, run_history=(run,), envelope_catalog=()
    )
    assert nav_a == nav_b


def test_timeline_contains_decision_summary_and_navigation() -> None:
    bus = RecordingInMemoryEventBus()
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle, verbose=False)
    fin = bundle.store.get(bundle.state_id).snapshot
    assert fin is not None
    merged = resolve_vertical_slice_inspection_catalog(bundle)
    text = render_vertical_slice_timeline_text(
        run_history=bundle.subscriber.run_history,
        envelope_catalog=merged,
        final_state=fin,
        include_operator_navigation=True,
    )
    assert "decision.summary=" in text or "score.summary=" in text
    assert "operator navigation" in text
    nav_txt = render_operator_navigation_text(
        final_state=fin,
        run_history=bundle.subscriber.run_history,
        envelope_catalog=merged,
    )
    assert "final.pipeline.phase=deep_scored" in nav_txt
