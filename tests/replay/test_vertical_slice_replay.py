"""
Deterministic replay harness for the recruiter vertical slice.

Replays the canonical ingress sequence twice with identical wiring contracts and
asserts structural equality of state, orchestration runs, and bus timelines.

Requires stable orchestration/bus identifiers (uuid5-derived) and envelope clocks;
see ``orchestrator.orchestrator`` and ``runtime.in_memory_event_bus``.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from orchestrator.orchestrator import OrchestrationExecutionResult
from runtime.bootstrap_vertical_slice import (
    PRIMARY_VERTICAL_SLICE_EVENT_TYPES,
    VerticalSliceRuntimeBundle,
    drive_vertical_slice_primary_sequence,
    wire_vertical_slice_runtime,
)
from schemas.state_schema import OrchestrationState, PipelinePhase

from tests.replay.recording_bus import RecordingInMemoryEventBus


def _json_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    raise TypeError(f"unsupported model type: {type(model)!r}")


def _runs_payload(runs: List[OrchestrationExecutionResult]) -> List[Dict[str, Any]]:
    return [_json_dict(r) for r in runs]


def _envelopes_payload(envelopes: List[EventEnvelope]) -> List[Dict[str, Any]]:
    return [_json_dict(e) for e in envelopes]


def _drive_bundle(bus: RecordingInMemoryEventBus) -> VerticalSliceRuntimeBundle:
    bundle = wire_vertical_slice_runtime(bus=bus)
    drive_vertical_slice_primary_sequence(bundle, verbose=False)
    return bundle


def test_vertical_slice_replay_twice_identical() -> None:
    """Two independent runtime stacks fed the same ingress sequence yield identical artifacts."""
    bus_a = RecordingInMemoryEventBus()
    bus_b = RecordingInMemoryEventBus()

    bundle_a = _drive_bundle(bus_a)
    bundle_b = _drive_bundle(bus_b)

    final_a = bundle_a.store.get(bundle_a.state_id).snapshot
    final_b = bundle_b.store.get(bundle_b.state_id).snapshot
    assert final_a is not None and final_b is not None
    assert isinstance(final_a, OrchestrationState) and isinstance(final_b, OrchestrationState)

    assert final_a.pipeline.phase == PipelinePhase.DEEP_SCORED
    assert final_b.pipeline.phase == PipelinePhase.DEEP_SCORED

    assert len(final_a.transitions) == 8
    assert len(final_b.transitions) == 8

    # One orchestration run per ingress publish, plus one nested run for emitted
    # ``questionnaire_requested`` after ``light_scoring_completed``.
    assert len(bundle_a.subscriber.run_history) == 9
    assert len(bundle_b.subscriber.run_history) == 9

    assert _json_dict(final_a) == _json_dict(final_b)

    assert _runs_payload(bundle_a.subscriber.run_history) == _runs_payload(bundle_b.subscriber.run_history)

    assert len(bus_a.recorded_envelopes) == len(PRIMARY_VERTICAL_SLICE_EVENT_TYPES) + 1
    assert len(bus_b.recorded_envelopes) == len(bus_a.recorded_envelopes)
    assert _envelopes_payload(bus_a.recorded_envelopes) == _envelopes_payload(bus_b.recorded_envelopes)

    # Explicit scoring / filter payloads from skill executions (subset of skill_results).
    scores_a = _scoring_rows(bundle_a.subscriber.run_history)
    scores_b = _scoring_rows(bundle_b.subscriber.run_history)
    assert scores_a == scores_b

    decisions_a = _decision_rows(bundle_a.subscriber.run_history)
    decisions_b = _decision_rows(bundle_b.subscriber.run_history)
    assert decisions_a == decisions_b


def _scoring_rows(runs: List[OrchestrationExecutionResult]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for run in runs:
        for sr in run.skill_results:
            pl = sr.output.payload if sr.output else {}
            row: Dict[str, Any] = {
                "skill": sr.metadata.skill_name,
                "status": sr.status.value,
            }
            if "scoring.normalized_score" in pl:
                row["scoring.normalized_score"] = pl["scoring.normalized_score"]
            if "scoring.deep.normalized_score" in pl:
                row["scoring.deep.normalized_score"] = pl["scoring.deep.normalized_score"]
            if "filter.decision" in pl:
                row["filter.decision"] = pl["filter.decision"]
            rows.append(row)
    return rows


def _decision_rows(runs: List[OrchestrationExecutionResult]) -> List[tuple]:
    out: List[tuple] = []
    for run in runs:
        for d in run.decisions:
            out.append((d.kind.value, d.code, d.message))
    return out

