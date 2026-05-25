"""API: cv_submitted ingress and score-sorted candidate list."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


_CV_HIGH = """
Senior Dev
dev@corp.io
10 years of experience
Python Django PostgreSQL REST API SQL testing git docker
"""

_CV_LOW = """
Junior
junior@test.io
1 years
"""


def test_cv_submitted_via_events_and_list_sort(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    establish_ready_scoring_context(client.app.state.vertical_slice)
    cid_high = str(uuid4())
    cid_low = str(uuid4())
    r_high = client.post(
        "/events",
        json={
            "event_type": "cv_submitted",
            "candidate_id": cid_high,
            "payload": {"cv_text": _CV_HIGH},
        },
    )
    assert r_high.status_code == 200, r_high.text

    r_low = client.post(
        "/events",
        json={
            "event_type": "cv_submitted",
            "candidate_id": cid_low,
            "payload": {"cv_text": _CV_LOW},
        },
    )
    assert r_low.status_code == 200, r_low.text

    view_high = client.get(f"/candidate/{cid_high}").json()
    view_low = client.get(f"/candidate/{cid_low}").json()
    assert view_high["evaluation"]["light"]["source"] == "system_llm"
    assert view_high["profile"]["summary"]
    assert view_high["decision"]["current_outcome"] == "undecided"
    assert view_high["scores"]["overall_score"]["value"] is not None
    assert view_low["scores"]["overall_score"]["value"] is not None
    assert view_high["scores"]["overall_score"]["value"] > view_low["scores"]["overall_score"]["value"]

    listing = client.get("/candidates").json()
    ids = [row["candidate_id"] for row in listing]
    assert ids.index(cid_high) < ids.index(cid_low)


def test_cv_submitted_requires_ready_scoring_context(client: TestClient) -> None:
    cid = str(uuid4())
    r = client.post(
        "/events",
        json={
            "event_type": "cv_submitted",
            "candidate_id": cid,
            "payload": {"cv_text": _CV_HIGH},
        },
    )
    assert r.status_code == 409
    assert r.json()["detail"]["code"] == "scoring_context_not_ready"


def test_cv_submitted_scoring_failure_returns_502(
    monkeypatch: pytest.MonkeyPatch,
    establish_ready_scoring_context,
) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    with TestClient(create_app(db_path="")) as client:
        establish_ready_scoring_context(client.app.state.vertical_slice)
        cid = str(uuid4())
        r = client.post(
            "/events",
            json={
                "event_type": "cv_submitted",
                "candidate_id": cid,
                "payload": {"cv_text": _CV_HIGH},
            },
        )
        assert r.status_code == 502
        assert r.json()["detail"] == {"status": "failed", "error": "scoring_failed"}
