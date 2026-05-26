from __future__ import annotations

from interfaces.skill_interface import ExecutionContext, ExecutionStatus, SkillInputEnvelope
from skills.llm.llm_provider import StubLLMProvider
from skills.llm.scoring_context_materialize_from_prose import (
    ScoringContextMaterializeFromProseSkill,
)


def test_scoring_context_materialize_skill_normalizes_prose() -> None:
    skill = ScoringContextMaterializeFromProseSkill(provider=StubLLMProvider())
    result = skill.execute(
        SkillInputEnvelope(
            payload={
                "vertical_slice.planner_path": "scoring_context_refresh",
                "organization_authoring_text": (
                    "BlueOcean is a recruitment company. The Talent Ops team operates in a "
                    "fast-moving recruiter workflow. The organization values clear "
                    "communication and structured follow-through."
                ),
                "recruiter_actor_authoring_text": (
                    "Recruiter test-recruiter is a lead recruiter focused on operator-ready "
                    "execution. The recruiter values stakeholder communication and ownership, "
                    "and avoids unclear communication."
                ),
                "job_authoring_text": (
                    "We are hiring for a Recruiting Operations Specialist. Must-have signals "
                    "include stakeholder communication and process ownership. Preferred signals "
                    "include ATS familiarity. Success in the role means keeping candidate flow "
                    "organized. Responsibilities include coordinating interviews and surfacing "
                    "blockers early."
                ),
            }
        ),
        ExecutionContext(run_reason="test"),
    )
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.output is not None
    payload = result.output.payload
    assert payload["organization_context"]["company_name"] == "BlueOcean"
    assert payload["recruiter_actor_context"]["actor_id"] == "test-recruiter"
    assert payload["job_context"]["title"] == "Recruiting Operations Specialist"
    assert payload["derived_l2_criteria"]
    assert payload["derived_l3_criteria"]
