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


def test_submit_cv_persists_extensions() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    result = submit_cv(rt, cid, _CV)
    assert result.ingress_accepted is True

    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    snap = got.snapshot
    assert snap.pipeline.phase == PipelinePhase.LIGHT_SCORED
    assert snap.ingress_profile is not None
    assert snap.evaluation is not None
    assert snap.evaluation.light is not None
    assert snap.ingress_profile.summary
    assert snap.evaluation.light.normalized_score is not None
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
