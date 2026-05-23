"""SQLite round-trip for CV snapshot extensions."""

from __future__ import annotations

from uuid import uuid4

from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import publish_recruitment_event, submit_cv

_CV = "Pat Lee\npat@co.dev\n10 years experience\nPython SQL API testing"


def test_sqlite_cv_extensions_survive_reload(tmp_path) -> None:
    db = str(tmp_path / "cv.sqlite")
    cid = uuid4()
    rt = VerticalSliceApiRuntime(db_path=db)
    publish_recruitment_event(rt, cid, "candidate_created", {})
    submit_cv(rt, cid, _CV)
    rt.bundle.store.close()

    rt2 = VerticalSliceApiRuntime(db_path=db)
    got = rt2.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None
    ext = got.snapshot.extensions
    assert ext.get("cv.raw_text")
    assert ext.get("cv.signals")
    assert ext.get("decision.light_score") is not None
    rt2.bundle.store.close()
