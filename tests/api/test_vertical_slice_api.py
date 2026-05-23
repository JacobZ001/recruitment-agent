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
    with TestClient(create_app(db_path="")) as c:
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


def test_post_events_accepts_new_candidate_id(client: TestClient) -> None:
    cid = str(uuid4())
    r = client.post(
        "/events",
        json={
            "event_type": "candidate_created",
            "candidate_id": cid,
        },
    )
    assert r.status_code == 200
    assert client.get(f"/state/{cid}").status_code == 200


def test_admin_reset_in_memory_restores_new(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    client.post("/events", json={"event_type": "candidate_created"})
    client.post("/events", json={"event_type": "cv_uploaded"})
    assert (
        client.get(f"/state/{cid}").json()["pipeline_phase"] == PipelinePhase.CV_RECEIVED.value
    )

    r = client.post("/admin/reset")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["sqlite_tables_cleared"] is False
    assert body["pipeline_phase"] == PipelinePhase.NEW.value

    assert client.get(f"/state/{cid}").json()["pipeline_phase"] == PipelinePhase.NEW.value


def test_admin_reset_sqlite_truncates_and_restores(tmp_path) -> None:
    import sqlite3

    db = tmp_path / "reset.db"
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    with TestClient(create_app(db_path=str(db))) as client:
        client.post("/events", json={"event_type": "candidate_created"})
        client.post("/events", json={"event_type": "cv_uploaded"})
        assert (
            client.get(f"/state/{cid}").json()["pipeline_phase"]
            == PipelinePhase.CV_RECEIVED.value
        )

        r = client.post("/admin/reset")
        assert r.status_code == 200
        body = r.json()
        assert body["sqlite_tables_cleared"] is True
        assert body["pipeline_phase"] == PipelinePhase.NEW.value
        assert body["store_revision"] == 1

        conn = sqlite3.connect(str(db))
        assert conn.execute("SELECT COUNT(*) FROM orchestration_state").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM state_transition_audit").fetchone()[0] == 0
        conn.close()

        client.post("/events", json={"event_type": "candidate_created"})
        assert (
            client.get(f"/state/{cid}").json()["pipeline_phase"] == PipelinePhase.NEW.value
        )
