"""CV ingestion via submit_cv and cv_submitted."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import submit_cv
from schemas.state_schema import PipelinePhase

_CV = """
Sam Recruiter
sam@hire.test
7 years of experience. Python, Django, PostgreSQL, API design.
"""


def test_submit_cv_persists_extensions(establish_ready_scoring_context) -> None:
    rt = VerticalSliceApiRuntime()
    establish_ready_scoring_context(rt)
    cid = uuid4()
    result = submit_cv(rt, cid, _CV)
    assert result.ingress_accepted is True

    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    snap = got.snapshot
    assert snap.pipeline.phase == PipelinePhase.QUESTIONNAIRE_PENDING
    got_c = rt.candidate_store.get(cid)
    assert got_c.ok and got_c.candidate is not None
    evaluation = got_c.candidate.evaluation_status
    assert evaluation.light is not None
    assert got_c.candidate.profile.summary
    assert evaluation.light.normalized_score is not None
    assert evaluation.light.context_version >= 1
    assert snap.evaluation_status_ref is not None
    assert "cv.raw_text" not in snap.extensions
    assert snap.decision.current_outcome.value == "undecided"


def test_submit_cv_empty_raises() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    try:
        submit_cv(rt, cid, "   ")
    except Exception as exc:
        assert "cv_text" in str(exc).lower()
    else:
        raise AssertionError("expected InvalidIngressEventError")
