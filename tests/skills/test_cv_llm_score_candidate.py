from __future__ import annotations

from interfaces.skill_interface import ExecutionContext, ExecutionStatus, SkillInputEnvelope
from schemas.state_schema import JobContext, OrganizationContext, RecruiterActorContext, ScoringContext
from skills.llm.cv_llm_score_candidate import CvLlmScoreCandidateSkill
from skills.llm.llm_provider import StubLLMProvider


def _dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def test_cv_score_candidate_consumes_persisted_derived_criteria() -> None:
    scoring_context = ScoringContext(
        context_version=7,
        status="ready",
        organization_context=OrganizationContext(
            company_name="BlueOcean",
            environment_signals=["fast-moving recruiter workflow"],
            preference_signals=["clear communication"],
        ),
        recruiter_actor_context=RecruiterActorContext(
            actor_id="test-recruiter",
            preference_signals=["ownership"],
            avoid_signals=["unclear communication"],
        ),
        job_context=JobContext(
            title="Recruiting Operations Specialist",
            responsibilities=["coordinate interviews"],
            hard_requirements=["this should not be used"],
            preferred_requirements=["nor this"],
            success_signals=["or this"],
        ),
        derived_l2_criteria=["Persisted custom L2 criterion"],
        derived_l3_criteria=["Persisted custom L3 criterion"],
    )
    skill = CvLlmScoreCandidateSkill(provider=StubLLMProvider())
    result = skill.execute(
        SkillInputEnvelope(
            payload={
                "vertical_slice.planner_path": "light_scoring_completed",
                "cv_text": "Candidate with ownership and communication experience",
                "profile": {},
                "scoring_context": _dump_model(scoring_context),
            }
        ),
        ExecutionContext(run_reason="test"),
    )
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.output is not None
    payload = result.output.payload["evaluation"]["light"]
    assert list(payload["l2_role_specific"]["criteria"].keys()) == ["Persisted custom L2 criterion"]
    assert list(payload["l3_recruiter_preference"]["criteria"].keys()) == [
        "Persisted custom L3 criterion"
    ]
