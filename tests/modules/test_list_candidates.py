"""list_candidates use case and build_candidate_list_item projection."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.scoring_context_service import build_score_evaluation
from modules.recruitment.projection import build_candidate_list_item
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import list_candidates, publish_recruitment_event
from runtime.in_memory_state_store import InMemoryStateStore
from schemas.state_schema import EvaluationState, PipelinePhase


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
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None and got_c.meta is not None
    evaluation = EvaluationState(
        light=build_score_evaluation(
            source="test",
            explanation="test",
            context_version=1,
            l1_universal={"communication": {"score": 0.82, "confidence": 0.6, "reason": "test"}},
            l2_role_specific={"role_fit": {"score": 0.82, "confidence": 0.6, "reason": "test"}},
            l3_recruiter_preference={"preference_fit": {"score": 0.82, "confidence": 0.6, "reason": "test"}},
        )
    )
    cand = got_c.candidate.model_copy(update={"evaluation_status": evaluation})
    rt.candidate_store.replace(cand, expected_store_revision=got_c.meta.store_revision)
    item = build_candidate_list_item(got.snapshot, candidate=cand)
    assert item["overall_score"] == {"value": 0.82, "type": "light"}


def test_build_candidate_list_item_overall_score_deep_precedence() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None and got_c.meta is not None
    evaluation = EvaluationState(
        light=build_score_evaluation(
            source="test",
            explanation="light",
            context_version=1,
            l1_universal={"communication": {"score": 0.5, "confidence": 0.5, "reason": "light"}},
            l2_role_specific={"role_fit": {"score": 0.5, "confidence": 0.5, "reason": "light"}},
            l3_recruiter_preference={"preference_fit": {"score": 0.5, "confidence": 0.5, "reason": "light"}},
        ),
        deep=build_score_evaluation(
            source="test",
            explanation="deep",
            context_version=1,
            l1_universal={"communication": {"score": 0.91, "confidence": 0.7, "reason": "deep"}},
            l2_role_specific={"role_fit": {"score": 0.91, "confidence": 0.7, "reason": "deep"}},
            l3_recruiter_preference={"preference_fit": {"score": 0.91, "confidence": 0.7, "reason": "deep"}},
        ),
    )
    cand = got_c.candidate.model_copy(update={"evaluation_status": evaluation})
    rt.candidate_store.replace(cand, expected_store_revision=got_c.meta.store_revision)
    item = build_candidate_list_item(got.snapshot, candidate=cand)
    assert item["overall_score"] == {"value": 0.91, "type": "deep"}


def test_build_candidate_list_item_overall_score_null_when_absent() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None
    item = build_candidate_list_item(got.snapshot, candidate=got_c.candidate)
    assert item["overall_score"] == {"value": None, "type": None}

