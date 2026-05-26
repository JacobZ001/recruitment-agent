from __future__ import annotations

import os

import pytest

from modules.recruitment.use_cases import (
    author_job_context_from_text,
    author_organization_context_from_text,
    author_recruiter_actor_context_from_text,
    refresh_active_scoring_context,
)
from skills.llm.llm_provider import StubLLMProvider
from skills.llm.scoring_context_materialize_from_prose import (
    ScoringContextMaterializeFromProseSkill,
)


@pytest.fixture(autouse=True)
def _configure_stub_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    if "LLM_PROVIDER" not in os.environ:
        monkeypatch.setenv("LLM_PROVIDER", "stub")
    if "LLM_MODEL" not in os.environ:
        monkeypatch.setenv("LLM_MODEL", "stub-cv")


@pytest.fixture
def establish_ready_scoring_context():
    def _apply(runtime) -> None:
        author_organization_context_from_text(
            runtime,
            (
                "BlueOcean is a recruitment company and the Talent Ops team operates in a "
                "fast-moving recruiter workflow. The organization values clear communication "
                "and structured follow-through."
            ),
            source_ref="test://organization",
        )
        author_recruiter_actor_context_from_text(
            runtime,
            (
                "Recruiter test-recruiter is a lead recruiter focused on operator-ready execution. "
                "The recruiter values stakeholder communication and ownership, and avoids "
                "unclear communication."
            ),
            source_ref="test://recruiter",
        )
        author_job_context_from_text(
            runtime,
            (
                "We are hiring for a Recruiting Operations Specialist. Must-have signals include "
                "recruiter coordination, stakeholder communication, and process ownership. "
                "Preferred signals include ATS familiarity and reporting discipline. Success in "
                "the role means keeping the hiring workflow organized and surfacing risks early. "
                "Responsibilities include coordinating candidate flow and maintaining process hygiene."
            ),
            source_ref="test://job_text",
        )
        refresh_active_scoring_context(
            runtime,
            materializer=ScoringContextMaterializeFromProseSkill(provider=StubLLMProvider()),
        )

    return _apply
