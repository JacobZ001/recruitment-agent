"""SQLite round-trip for typed CV snapshot fields."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import (
    author_job_context_from_text,
    author_organization_context,
    author_recruiter_actor_context,
    refresh_active_scoring_context,
    submit_cv,
)
from schemas.state_schema import OrganizationContext, RecruiterActorContext

_CV = "Pat Lee\npat@co.dev\n10 years experience\nPython SQL API testing"


def test_sqlite_cv_extensions_survive_reload(tmp_path) -> None:
    db = str(tmp_path / "cv.sqlite")
    cid = uuid4()
    rt = VerticalSliceApiRuntime(db_path=db)
    author_organization_context(
        rt,
        OrganizationContext(
            company_name="BlueOcean",
            environment_signals=["structured recruiting operations"],
            preference_signals=["clear communication"],
            source_refs=["test://org"],
        ),
    )
    author_recruiter_actor_context(
        rt,
        RecruiterActorContext(
            actor_id="sqlite-test",
            preference_signals=["ownership"],
            avoid_signals=["unclear updates"],
            source_refs=["test://recruiter"],
        ),
    )
    author_job_context_from_text(
        rt,
        "Role: QA Recruiter\nMust: communication, process ownership\nSuccess: keep candidate flow on track",
        source_ref="test://job",
    )
    refresh_active_scoring_context(rt)
    submit_cv(rt, cid, _CV)
    rt.bundle.store.close()

    rt2 = VerticalSliceApiRuntime(db_path=db)
    got = rt2.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    assert got.snapshot.ingress_profile is not None
    assert got.snapshot.evaluation is not None
    assert got.snapshot.evaluation.light is not None
    assert got.snapshot.evaluation.light.normalized_score is not None
    assert "cv.raw_text" not in got.snapshot.extensions
    rt2.bundle.store.close()
