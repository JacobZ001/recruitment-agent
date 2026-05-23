"""CV ingestion via submit_cv and cv_submitted."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import publish_recruitment_event, submit_cv
from schemas.state_schema import PipelinePhase

_CV = """
Sam Recruiter
sam@hire.test
7 years of experience. Python, Django, PostgreSQL, API design.
"""


def test_submit_cv_persists_extensions() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {"source": "test"})
    result = submit_cv(rt, cid, _CV)
    assert result.ingress_accepted is True

    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    snap = got.snapshot
    assert snap.pipeline.phase == PipelinePhase.CV_PARSED
    ext = snap.extensions
    assert ext.get("cv.raw_text")
    assert isinstance(ext.get("cv.signals"), dict)
    assert ext["cv.signals"].get("matched_keywords")
    assert ext.get("decision.light_score") is not None


def test_submit_cv_empty_raises() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {})
    try:
        submit_cv(rt, cid, "   ")
    except Exception as exc:
        assert "cv_text" in str(exc).lower()
    else:
        raise AssertionError("expected InvalidIngressEventError")
