"""list_candidates use case and build_candidate_list_item projection."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.projection import build_candidate_list_item
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import list_candidates, publish_recruitment_event
from runtime.in_memory_state_store import InMemoryStateStore
from schemas.state_schema import EvaluationState, PipelinePhase, ScoreEvaluation


def test_in_memory_list_all_state_ids() -> None:
    store = InMemoryStateStore()
    cid = uuid4()
    from modules.recruitment.registry import get_state_id
    from modules.recruitment.state_init import initial_orchestration_state
    from modules.recruitment.ingress import FIXED_CLOCK

    sid = get_state_id(cid)
    store.create(
        initial_orchestration_state(
            state_id=sid,
            candidate_id=cid,
            occurred_at=FIXED_CLOCK,
        )
    )
    assert store.list_all_state_ids() == [sid]


def test_list_candidates_use_case() -> None:
    rt = VerticalSliceApiRuntime()
    cid_a = uuid4()
    cid_b = uuid4()
    publish_recruitment_event(rt, cid_a, "candidate_created", {})
    publish_recruitment_event(rt, cid_b, "candidate_created", {})
    publish_recruitment_event(rt, cid_a, "cv_uploaded", {})

    rows = list_candidates(rt)
    by_id = {r["candidate_id"]: r for r in rows}
    assert str(cid_a) in by_id
    assert str(cid_b) in by_id
    assert by_id[str(cid_a)]["stage"] == PipelinePhase.CV_RECEIVED.value
    assert by_id[str(cid_b)]["stage"] == PipelinePhase.NEW.value
    assert by_id[str(cid_a)]["rank"] is not None
    assert by_id[str(cid_a)]["total_candidates"] == len(rows)


def test_build_candidate_list_item_overall_score_light() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    snap = got.snapshot.model_copy(
        update={
            "evaluation": EvaluationState(
                light=ScoreEvaluation(
                    normalized_score=0.82,
                    confidence=0.6,
                    explanation="test",
                    source="test",
                )
            )
        },
    )
    item = build_candidate_list_item(snap)
    assert item["overall_score"] == {"value": 0.82, "type": "light"}


def test_build_candidate_list_item_overall_score_deep_precedence() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    snap = got.snapshot.model_copy(
        update={
            "evaluation": EvaluationState(
                light=ScoreEvaluation(
                    normalized_score=0.5,
                    confidence=0.5,
                    explanation="light",
                    source="test",
                ),
                deep=ScoreEvaluation(
                    normalized_score=0.91,
                    confidence=0.7,
                    explanation="deep",
                    source="test",
                ),
            )
        },
    )
    item = build_candidate_list_item(snap)
    assert item["overall_score"] == {"value": 0.91, "type": "deep"}


def test_build_candidate_list_item_overall_score_null_when_absent() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    item = build_candidate_list_item(got.snapshot)
    assert item["overall_score"] == {"value": None, "type": None}

