from __future__ import annotations

import os

import pytest

from modules.recruitment.use_cases import (
    author_job_context_from_text,
    author_organization_context,
    author_recruiter_actor_context,
    refresh_active_scoring_context,
)
from schemas.state_schema import OrganizationContext, RecruiterActorContext


@pytest.fixture(autouse=True)
def _configure_stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    if "LLM_PROVIDER" not in os.environ:
        monkeypatch.setenv("LLM_PROVIDER", "stub")
    if "LLM_MODEL" not in os.environ:
        monkeypatch.setenv("LLM_MODEL", "stub-cv")


@pytest.fixture
def establish_ready_scoring_context():
    def _apply(runtime) -> None:
        author_organization_context(
            runtime,
            OrganizationContext(
                company_name="BlueOcean",
                industry="recruitment",
                team_name="Talent Ops",
                environment_signals=["fast-moving recruiter workflow"],
                preference_signals=["clear communication", "structured follow-through"],
                summary="Single-tenant recruiter evaluation baseline.",
                source_refs=["test://organization"],
            ),
        )
        author_recruiter_actor_context(
            runtime,
            RecruiterActorContext(
                actor_id="test-recruiter",
                actor_role="lead_recruiter",
                hiring_focus=["operator-ready execution"],
                preference_signals=["stakeholder communication", "ownership"],
                avoid_signals=["unclear communication"],
                summary="Default recruiter preference context for deterministic tests.",
                source_refs=["test://recruiter"],
            ),
        )
        author_job_context_from_text(
            runtime,
            "\n".join(
                [
                    "Role: Recruiting Operations Specialist",
                    "Must: recruiter coordination, stakeholder communication, process ownership",
                    "Preferred: ATS familiarity, reporting discipline",
                    "Success: keep hiring workflow organized, surface risks early",
                    "Responsibilities: coordinate candidate flow, maintain process hygiene",
                ]
            ),
            source_ref="test://job_text",
        )
        refresh_active_scoring_context(runtime)

    return _apply
