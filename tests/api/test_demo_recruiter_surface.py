"""Thin recruiter demo surface: fixture JSON, scripted bus run, HTML smoke."""

from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from modules.recruitment.projection import CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER
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


def _assert_criteria_shape(crit: list) -> None:
    assert isinstance(crit, list)
    assert len(crit) >= 2
    for c in crit:
        assert "name" in c and isinstance(c["name"], str) and c["name"]
        assert "source" in c and c["source"] in (
            "universal",
            "role_specific",
            "recruiter_preference",
        )
        assert c.get("score") is None
        assert c.get("confidence") is None


def _assert_overall_score_shape(overall: dict) -> None:
    assert "value" in overall
    assert "type" in overall
    assert overall["type"] in ("light", "deep", None)


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
    assert data["summary"] == CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER
    assert data["decision"]["current_outcome"] == "undecided"
    assert data["evaluation"] is None
    assert data["flags"]["was_inactive"] is False
    _assert_criteria_shape(data["scores"]["criteria"])
    _assert_overall_score_shape(data["scores"]["overall_score"])
    assert data["scores"]["overall_score"]["value"] is None
    assert data["scores"]["overall_score"]["type"] is None
    assert data["ranking"]["rank"] is None
    assert data["ranking"]["total_candidates"] is None
    assert "branch" not in data["ranking"]
    assert "stage" not in data["ranking"]
    assert data["next_actions"] == []


def test_ranking_section_omits_snapshot_scoring_stage_keys(client: TestClient) -> None:
    """``ranking.stage`` / ``ranking.branch`` stay on snapshot for audit; not recruiter API."""
    assert client.post("/demo/run").status_code == 200
    data = client.get(f"/candidate/{VERTICAL_SLICE_DEFAULT_CANDIDATE_ID}").json()
    rt = client.app.state.vertical_slice
    ext = dict(rt.bundle.store.get_for_candidate(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID).snapshot.extensions)
    assert ext.get("ranking.stage") == "deep"
    assert "stage" not in data["ranking"]
    assert "branch" not in data["ranking"]
    assert data["scores"]["overall_score"]["type"] == "deep"


def test_get_candidate_after_demo_run_scores_and_ranking_match_extensions(client: TestClient) -> None:
    assert client.post("/demo/run").status_code == 200
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    data = client.get(f"/candidate/{cid}").json()
    assert data["stage"] == PipelinePhase.SHORTLISTED.value
    assert data["status"]["kind"] == "active"
    assert data["summary"] == CANDIDATE_VIEW_EVALUATION_SUMMARY_PLACEHOLDER

    _assert_criteria_shape(data["scores"]["criteria"])

    rt = client.app.state.vertical_slice
    got = rt.bundle.store.get_for_candidate(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert got.ok and got.snapshot is not None
    assert got.snapshot.evaluation is not None
    assert got.snapshot.evaluation.deep is not None

    overall = data["scores"]["overall_score"]
    _assert_overall_score_shape(overall)
    assert overall["type"] == "deep"
    assert overall["value"] == got.snapshot.evaluation.deep.normalized_score
    assert data["evaluation"]["deep"]["normalized_score"] == got.snapshot.evaluation.deep.normalized_score

    assert data["ranking"]["rank"] is None
    assert data["ranking"]["total_candidates"] is None
    assert "single-candidate" in (data["ranking"].get("note") or "")
    assert "stage" not in data["ranking"]
    assert "branch" not in data["ranking"]
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
    assert "Evaluation" in html
    assert "Ranking" in html
    assert "recruiter_schedule_interview" in html
    assert "candidate_accept_offer" in html
