"""Deterministic scoring-context lifecycle and candidate re-score semantics."""

from __future__ import annotations

from uuid import uuid4

import pytest

from modules.recruitment.exceptions import InvalidScoringContextError, ScoringContextNotReadyError
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import (
    author_job_context_from_recruiter_answers,
    author_organization_context,
    author_organization_context_from_text,
    author_recruiter_actor_context,
    author_recruiter_actor_context_from_text,
    get_active_scoring_context,
    publish_recruitment_event,
    refresh_active_scoring_context,
    submit_cv,
)
from schemas.state_schema import (
    OrganizationContext,
    PipelinePhase,
    RecruiterActorContext,
    ScoringContextStatus,
)


def test_scoring_context_status_transitions_and_re_score_staleness() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    assert get_active_scoring_context(rt) is None

    first = author_organization_context(
        rt,
        OrganizationContext(
            company_name="BlueOcean",
            environment_signals=["fast-moving ops"],
            preference_signals=["clear communication"],
        ),
    )
    assert first.status.value == "collecting"
    assert first.context_version == 1
    assert first.organization_authoring_text

    second = author_recruiter_actor_context(
        rt,
        RecruiterActorContext(
            actor_id="recruiter-a",
            preference_signals=["ownership"],
            avoid_signals=["unclear updates"],
        ),
    )
    assert second.status.value == "collecting"
    assert second.context_version == 2
    assert second.recruiter_actor_authoring_text

    third = author_job_context_from_recruiter_answers(
        rt,
        role_title="Operations Recruiter",
        must_haves_answer="stakeholder communication\nprocess ownership",
        preferred_answer="ATS familiarity",
        success_answer="keep candidate flow organized",
        responsibilities_answer="coordinate interviews\nsurface blockers early",
    )
    assert third.status.value == "collecting"
    assert third.context_version == 3
    assert third.job_authoring_text

    ready = refresh_active_scoring_context(rt)
    assert ready.status.value == "ready"
    assert ready.context_version == 3
    assert ready.derived_l2_criteria
    assert ready.derived_l3_criteria

    submit_cv(rt, cid, "Recruiter profile\n6 years\ncommunication and process ownership")
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    assert got.snapshot.pipeline.phase == PipelinePhase.QUESTIONNAIRE_PENDING
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None
    light = got_c.candidate.evaluation_status.light
    assert light is not None
    assert light.context_version == 3
    assert light.stale is False

    stale = author_organization_context(
        rt,
        OrganizationContext(
            company_name="BlueOcean",
            environment_signals=["high-context coordination"],
            preference_signals=["clear communication", "structured follow-through"],
        ),
    )
    assert stale.status.value == "stale"
    assert stale.context_version == 4

    got_stale = rt.bundle.store.get_for_candidate(cid)
    assert got_stale.ok and got_stale.snapshot is not None
    got_stale_c = rt.candidate_store.get(cid)
    assert got_stale_c.ok and got_stale_c.candidate is not None
    assert got_stale_c.candidate.evaluation_status.light is not None
    assert got_stale_c.candidate.evaluation_status.light.stale is True

    ready_again = refresh_active_scoring_context(rt)
    assert ready_again.status.value == "ready"
    assert ready_again.context_version == 4


def test_submit_cv_run_history_persists_profile_before_scoring(
    establish_ready_scoring_context,
) -> None:
    rt = VerticalSliceApiRuntime()
    establish_ready_scoring_context(rt)
    cid = uuid4()
    submit_cv(rt, cid, "Backend recruiter ops\n5 years\ncommunication ownership")
    runs = rt.bundle.subscriber.run_history[-3:]
    assert len(runs) == 3
    assert runs[0].new_state is not None
    assert runs[0].new_state.pipeline.phase == PipelinePhase.CV_RECEIVED
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None
    assert got_c.candidate.profile.summary
    assert runs[0].new_state.ingress_profile is None
    assert runs[1].new_state is not None
    assert runs[1].new_state.pipeline.phase == PipelinePhase.CV_PARSED
    assert runs[2].new_state is not None
    assert runs[2].new_state.evaluation is None
    assert got_c.candidate.evaluation_status.light is not None


def test_recruiter_answers_normalization_requires_role_title() -> None:
    rt = VerticalSliceApiRuntime()
    with pytest.raises(InvalidScoringContextError, match="role_title"):
        author_job_context_from_recruiter_answers(
            rt,
            role_title="",
            must_haves_answer="communication",
            preferred_answer="",
            success_answer="",
            responsibilities_answer="",
        )


def test_prose_authoring_materializes_on_refresh() -> None:
    rt = VerticalSliceApiRuntime()
    author_organization_context_from_text(
        rt,
        (
            "BlueOcean is a recruitment company. The Talent Ops team operates in a fast-moving "
            "workflow. The organization values clear communication and structured follow-through."
        ),
    )
    author_recruiter_actor_context_from_text(
        rt,
        (
            "Recruiter prose-recruiter is a lead recruiter focused on operator-ready execution. "
            "The recruiter values stakeholder communication and ownership, and avoids unclear updates."
        ),
    )
    author_job_context_from_recruiter_answers(
        rt,
        role_title="Operations Recruiter",
        must_haves_answer="stakeholder communication\nprocess ownership",
        preferred_answer="ATS familiarity",
        success_answer="keep candidate flow organized",
        responsibilities_answer="coordinate interviews\nsurface blockers early",
    )

    current = get_active_scoring_context(rt)
    assert current is not None
    assert current.organization_context is None
    assert current.recruiter_actor_context is None
    assert current.job_context is None

    ready = refresh_active_scoring_context(rt)
    assert ready.organization_context is not None
    assert ready.recruiter_actor_context is not None
    assert ready.job_context is not None
    assert ready.derived_l2_criteria
    assert ready.derived_l3_criteria


def test_refresh_requires_non_empty_derived_l2_and_l3_signals() -> None:
    rt = VerticalSliceApiRuntime()
    author_organization_context(
        rt,
        OrganizationContext(
            company_name="BlueOcean",
            environment_signals=["fast-moving ops"],
            preference_signals=[],
        ),
    )
    author_recruiter_actor_context(
        rt,
        RecruiterActorContext(
            actor_id="recruiter-a",
            preference_signals=[],
            avoid_signals=[],
        ),
    )
    author_job_context_from_recruiter_answers(
        rt,
        role_title="Operations Recruiter",
        must_haves_answer="stakeholder communication",
        preferred_answer="",
        success_answer="keep candidate flow organized",
        responsibilities_answer="coordinate interviews",
    )

    with pytest.raises(InvalidScoringContextError, match="normalized into typed context"):
        refresh_active_scoring_context(rt)

    current = get_active_scoring_context(rt)
    assert current is not None
    assert current.status == ScoringContextStatus.COLLECTING
    assert current.derived_l2_criteria == []
    assert current.derived_l3_criteria == []


def test_deep_scoring_requires_ready_scoring_context() -> None:
    rt = VerticalSliceApiRuntime()
    with pytest.raises(ScoringContextNotReadyError, match="scoring_context_not_ready"):
        publish_recruitment_event(rt, uuid4(), "deep_scoring_completed", {})


def test_deep_scoring_rejects_stale_scoring_context(establish_ready_scoring_context) -> None:
    rt = VerticalSliceApiRuntime()
    establish_ready_scoring_context(rt)
    author_organization_context(
        rt,
        OrganizationContext(
            company_name="BlueOcean",
            environment_signals=["high-context coordination"],
            preference_signals=["clear communication", "structured follow-through"],
        ),
    )
    with pytest.raises(ScoringContextNotReadyError, match="scoring_context_not_ready"):
        publish_recruitment_event(rt, uuid4(), "deep_scoring_completed", {})
