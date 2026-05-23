"""GET /candidates — multi-candidate list projection."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from schemas.state_schema import PipelinePhase


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_list_candidates_empty_except_bootstrap_default(client: TestClient) -> None:
    r = client.get("/candidates")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list)
    assert len(body) >= 1


def test_list_candidates_returns_all_created(client: TestClient) -> None:
    cid_a = str(uuid4())
    cid_b = str(uuid4())
    assert (
        client.post(
            "/events",
            json={"event_type": "candidate_created", "candidate_id": cid_a},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/events",
            json={"event_type": "candidate_created", "candidate_id": cid_b},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/events",
            json={"event_type": "cv_uploaded", "candidate_id": cid_a},
        ).status_code
        == 200
    )

    r = client.get("/candidates")
    assert r.status_code == 200
    by_id = {row["candidate_id"]: row for row in r.json()}
    assert cid_a in by_id
    assert cid_b in by_id
    assert by_id[cid_a]["stage"] == PipelinePhase.CV_RECEIVED.value
    assert by_id[cid_b]["stage"] == PipelinePhase.NEW.value
    assert by_id[cid_a]["status"]["kind"] == "active"
    assert by_id[cid_a]["overall_score"] == {"value": None, "type": None}
    assert "criteria" not in by_id[cid_a]
    assert "summary" not in by_id[cid_a]


def test_list_candidates_no_cross_contamination(client: TestClient) -> None:
    cid_a = str(uuid4())
    cid_b = str(uuid4())
    client.post("/events", json={"event_type": "candidate_created", "candidate_id": cid_a})
    client.post("/events", json={"event_type": "candidate_created", "candidate_id": cid_b})
    client.post("/events", json={"event_type": "cv_uploaded", "candidate_id": cid_a})

    rows = client.get("/candidates").json()
    phases = {row["candidate_id"]: row["stage"] for row in rows if row["candidate_id"] in (cid_a, cid_b)}
    assert phases[cid_a] == PipelinePhase.CV_RECEIVED.value
    assert phases[cid_b] == PipelinePhase.NEW.value
