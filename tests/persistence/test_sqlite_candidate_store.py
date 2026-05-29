"""SQLite candidate store (R-009)."""

from __future__ import annotations

from uuid import uuid4

from runtime.persistence.sqlite_candidate_store import SQLiteCandidateStore
from schemas.candidate_schema import Candidate, new_candidate


def test_sqlite_candidate_store_create_get_replace(tmp_path) -> None:
    db = tmp_path / "candidates.db"
    store = SQLiteCandidateStore(str(db))
    cid = uuid4()
    cand = new_candidate(cid, updated_by="test")
    created = store.create(cand)
    assert created.ok

    got = store.get(cid)
    assert got.ok and got.candidate is not None
    assert got.candidate.candidate_id == cid

    updated = got.candidate.model_copy(
        update={
            "identity": got.candidate.identity.model_copy(update={"full_name": "Alex Test"}),
        }
    )
    rep = store.replace(updated, expected_store_revision=got.meta.store_revision)
    assert rep.ok
    assert rep.candidate is not None
    assert rep.candidate.identity.full_name == "Alex Test"
