"""API: R-013 dedup block, suspected flag, governance actions."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from modules.recruitment.dedup import normalize_email
from runtime.persistence.in_memory_candidate_store import InMemoryCandidateStore
from schemas.candidate_schema import Candidate, DedupSignals, Identity, new_candidate
from tests.api.test_cv_pdf_ingest import _build_pdf_base64


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def _seed_candidate_with_email(rt, email: str) -> str:
    store: InMemoryCandidateStore = rt.candidate_store
    cid = uuid4()
    cand = new_candidate(cid)
    cand = cand.model_copy(
        update={
            "identity": Identity(primary_email=email, full_name="Existing Person"),
            "dedup_signals": DedupSignals(normalized_email=normalize_email(email)),
        }
    )
    store.create(cand)
    from modules.recruitment.use_cases import _ensure_candidate_state

    _ensure_candidate_state(rt, cid)
    return str(cid)


def test_create_cv_pdf_blocks_high_confidence_email_duplicate(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    rt = client.app.state.vertical_slice
    establish_ready_scoring_context(rt)
    _seed_candidate_with_email(rt, "dup.block@hire.test")
    pdf_text = "dup.block@hire.test\nSenior engineer\nPython"
    r = client.post(
        "/candidates/cv/pdf",
        headers={"Idempotency-Key": str(uuid4())},
        json={"pdf_base64": _build_pdf_base64(pdf_text), "file_name": "cv.pdf"},
    )
    assert r.status_code == 409
    body = r.json()
    assert body["detail"]["code"] == "duplicate_candidate_high_confidence"
    assert body["detail"]["matches"]


def test_dedup_link_and_keep_separate(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    rt = client.app.state.vertical_slice
    establish_ready_scoring_context(rt)
    existing_id = _seed_candidate_with_email(rt, "link.test@hire.test")
    cid = uuid4()
    from modules.recruitment.use_cases import _ensure_candidate_state

    _ensure_candidate_state(rt, cid)
    got = rt.candidate_store.get(cid)
    assert got.ok and got.candidate is not None and got.meta is not None
    flagged = got.candidate.model_copy(
        update={
            "extensions": {
                **got.candidate.extensions,
                "dedup": {
                    "status": "suspected_duplicate",
                    "pending_resolution": True,
                    "matches": [{"candidate_id": existing_id, "match_kinds": ["cv_content_fingerprint"]}],
                    "audit": [],
                },
            }
        }
    )
    rt.candidate_store.replace(flagged, expected_store_revision=got.meta.store_revision)
    link = client.post(
        f"/candidates/{cid}/dedup/link",
        json={
            "target_candidate_id": existing_id,
            "actor_id": "recruiter-test",
            "reason": "Same person different upload",
        },
    )
    assert link.status_code == 200
    assert link.json()["dedup_status"] == "linked"
    assert link.json()["dedup_linked_to_candidate_id"] == existing_id

    cid2 = uuid4()
    _ensure_candidate_state(rt, cid2)
    got2 = rt.candidate_store.get(cid2)
    assert got2.ok and got2.candidate is not None and got2.meta is not None
    flagged2 = got2.candidate.model_copy(
        update={
            "extensions": {
                **got2.candidate.extensions,
                "dedup": {"status": "suspected_duplicate", "pending_resolution": True, "audit": []},
            }
        }
    )
    rt.candidate_store.replace(flagged2, expected_store_revision=got2.meta.store_revision)
    keep = client.post(
        f"/candidates/{cid2}/dedup/keep-separate",
        json={"actor_id": "recruiter-test", "reason": "Distinct applicant"},
    )
    assert keep.status_code == 200
    assert keep.json()["dedup_status"] == "keep_separate"
    assert keep.json()["dedup_pending_resolution"] is False
