"""CvLlmParseAndScoreSkill contract tests."""

from __future__ import annotations

from uuid import uuid4

import pytest

from interfaces.skill_interface import ExecutionContext, ExecutionStatus, SkillInputEnvelope
from skills.llm.cv_llm_parse_and_score import CvLlmParseAndScoreSkill
from skills.llm.llm_provider import StubLLMProvider


_CV = """
Alex Dev
alex@dev.io
5 years experience with Python and REST APIs.
"""


def _context() -> ExecutionContext:
    return ExecutionContext(
        event_id=uuid4(),
        subject_id=uuid4(),
        correlation_id=uuid4(),
    )


def test_skill_requires_cv_text() -> None:
    skill = CvLlmParseAndScoreSkill(provider=StubLLMProvider())
    result = skill.execute(
        SkillInputEnvelope(
            payload={
                "vertical_slice.planner_path": "cv_submitted",
                "ingested_event_id": "e1",
                "ingested_event_type": "cv_submitted",
            }
        ),
        _context(),
    )
    assert result.status == ExecutionStatus.FAILED
    assert result.failure is not None
    assert "cv_text" in result.failure.message


def test_skill_success_emits_typed_payload() -> None:
    skill = CvLlmParseAndScoreSkill(provider=StubLLMProvider())
    result = skill.execute(
        SkillInputEnvelope(
            payload={
                "vertical_slice.planner_path": "cv_submitted",
                "ingested_event_id": "e1",
                "ingested_event_type": "cv_submitted",
                "cv_text": _CV,
            }
        ),
        _context(),
    )
    assert result.status == ExecutionStatus.SUCCEEDED
    assert result.output is not None
    pl = result.output.payload
    assert "profile" in pl
    assert "evaluation" in pl
    assert "light" in pl["evaluation"]
    assert "summary" in pl["profile"]
    assert "normalized_score" in pl["evaluation"]["light"]
    assert "cv.raw_text" not in pl
    assert "cv.signals" not in pl
