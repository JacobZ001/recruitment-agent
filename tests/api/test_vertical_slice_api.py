"""FastAPI ingress boundary for the vertical slice (thin adapter only)."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from runtime.bootstrap_vertical_slice import VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
from schemas.state_schema import PipelinePhase


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as c:
        yield c


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sync"] is True
    assert "vertical_slice" in body["runtime"]


def test_post_events_one_event_returns_publish_and_state_summary(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    r = client.post(
        "/events",
        json={
            "event_type": "candidate_created",
            "candidate_id": cid,
            "payload": {"source": "api_test"},
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ingress_accepted"] is True
    assert body["publish_status"] == "accepted"
    assert body["event_type"] == "candidate_created"
    assert "event_id" in body
    assert body["state_summary"]["pipeline_phase"] == PipelinePhase.NEW.value


def test_sequential_events_progress_pipeline(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert (
        client.post("/events", json={"event_type": "candidate_created"}).status_code == 200
    )
    assert client.post("/events", json={"event_type": "cv_uploaded"}).status_code == 200

    st = client.get(f"/state/{cid}")
    assert st.status_code == 200
    assert st.json()["pipeline_phase"] == PipelinePhase.CV_RECEIVED.value


def test_timeline_returns_inspection_text(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    client.post("/events", json={"event_type": "candidate_created"})
    tr = client.get(f"/timeline/{cid}")
    assert tr.status_code == 200
    data = tr.json()
    assert "workflow timeline" in data["timeline_text"]
    assert data["catalog_note"] is None or isinstance(data["catalog_note"], str)


def test_invalid_event_type_returns_422(client: TestClient) -> None:
    r = client.post("/events", json={"event_type": "not_a_real_vertical_slice_event"})
    assert r.status_code == 422


def test_unknown_candidate_returns_404(client: TestClient) -> None:
    bad = str(uuid4())
    r = client.get(f"/state/{bad}")
    assert r.status_code == 404


def test_post_events_wrong_candidate_returns_404(client: TestClient) -> None:
    r = client.post(
        "/events",
        json={
            "event_type": "candidate_created",
            "candidate_id": str(uuid4()),
        },
    )
    assert r.status_code == 404
