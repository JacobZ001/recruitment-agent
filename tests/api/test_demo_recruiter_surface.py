"""Thin recruiter demo surface: fixture JSON, scripted bus run, HTML smoke."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from runtime.bootstrap_vertical_slice import VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
from schemas.state_schema import PipelinePhase


_GOVERNANCE_PAYLOAD = {
    "actor_id": "api-test-recruiter",
    "actor_type": "recruiter",
    "reason": "API deterministic governance test",
    "evidence_refs": ["artifact://api/test"],
}


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_get_demo_candidate_returns_fixture_profile(client: TestClient) -> None:
    r = client.get("/demo/candidate")
    assert r.status_code == 200
    data = r.json()
    assert data["profile"]["candidate_name"] == "Alex Morgan"
    assert data["candidate_id"] == str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert data["pipeline_phase"] == PipelinePhase.NEW.value


def test_get_candidate_by_id_returns_projection(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    r = client.get(f"/candidate/{cid}")
    assert r.status_code == 200
    data = r.json()
    assert data["candidate_id"] == cid
    assert data["stage"] == PipelinePhase.NEW.value
    assert data["status"]["kind"] == "active"
    assert "pipeline" in data["summary"].lower() or "new" in data["summary"].lower()
    assert data["next_actions"] == []


def test_get_candidate_after_demo_run_includes_ranking_and_scores(client: TestClient) -> None:
    assert client.post("/demo/run").status_code == 200
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    data = client.get(f"/candidate/{cid}").json()
    assert data["stage"] == PipelinePhase.SHORTLISTED.value
    assert data["status"]["kind"] == "active"
    assert data["ranking"].get("branch") == "top_k"
    assert data["ranking"].get("stage") == "deep"
    assert data["ranking"].get("explanation")
    assert "light" in data["scores"]
    assert "deep" in data["scores"]
    assert data["next_actions"]


def test_get_candidate_view_offer_sent_stage_is_authoritative(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert client.post("/demo/run").status_code == 200
    for et in (
        "recruiter_schedule_interview",
        "recruiter_complete_interview",
        "recruiter_send_offer",
    ):
        r = client.post("/events", json={"event_type": et, "payload": dict(_GOVERNANCE_PAYLOAD)})
        assert r.status_code == 200
        assert r.json()["ingress_accepted"] is True
    data = client.get(f"/candidate/{cid}").json()
    assert data["stage"] == PipelinePhase.OFFER_SENT.value
    assert data["status"]["kind"] == "active"


def test_get_candidate_wrong_id_returns_404(client: TestClient) -> None:
    r = client.get(f"/candidate/{uuid4()}")
    assert r.status_code == 404


def test_post_demo_run_advances_to_shortlisted(client: TestClient) -> None:
    r = client.post("/demo/run")
    assert r.status_code == 200
    body = r.json()
    assert body["state_summary"]["pipeline_phase"] == PipelinePhase.SHORTLISTED.value

    cand = client.get("/demo/candidate").json()
    assert cand["pipeline_phase"] == PipelinePhase.SHORTLISTED.value
    hf = cand["skill_summaries"].get("hard_filter") or {}
    assert "decision.summary" in hf or "filter.decision" in str(hf)


def test_post_demo_run_twice_returns_409(client: TestClient) -> None:
    assert client.post("/demo/run").status_code == 200
    r2 = client.post("/demo/run")
    assert r2.status_code == 409


def test_api_post_governance_hire_ladder_updates_phase_and_timeline(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert client.post("/demo/run").status_code == 200
    for et in (
        "recruiter_schedule_interview",
        "recruiter_complete_interview",
        "recruiter_send_offer",
        "candidate_accept_offer",
    ):
        r = client.post("/events", json={"event_type": et, "payload": dict(_GOVERNANCE_PAYLOAD)})
        assert r.status_code == 200
        assert r.json()["ingress_accepted"] is True
    st = client.get(f"/state/{cid}").json()
    assert st["pipeline_phase"] == PipelinePhase.HIRED.value
    tl = client.get(f"/timeline/{cid}").json()["timeline_text"]
    assert "CANDIDATE_ACCEPT_OFFER" in tl
    assert "final.pipeline.phase=hired" in tl


def test_demo_html_contains_profile_phase_timeline_and_scores(client: TestClient) -> None:
    client.post("/demo/run")
    html = client.get("/demo").text
    assert "Alex Morgan" in html
    assert "shortlisted" in html
    assert "workflow timeline" in html
    assert "Scores" in html
    assert "Ranking" in html
    assert "recruiter_schedule_interview" in html
    assert "candidate_accept_offer" in html
