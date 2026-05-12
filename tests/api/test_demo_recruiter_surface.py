"""Thin recruiter demo surface: fixture JSON, scripted bus run, HTML smoke."""

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


def test_get_demo_candidate_returns_fixture_profile(client: TestClient) -> None:
    r = client.get("/demo/candidate")
    assert r.status_code == 200
    data = r.json()
    assert data["profile"]["candidate_name"] == "Alex Morgan"
    assert data["candidate_id"] == str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert data["pipeline_phase"] == PipelinePhase.NEW.value


def test_get_candidate_by_id_matches_demo_fixture(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    r = client.get(f"/candidate/{cid}")
    assert r.status_code == 200
    assert r.json()["profile"]["target_role"] == "Senior Backend Engineer"


def test_get_candidate_wrong_id_returns_404(client: TestClient) -> None:
    r = client.get(f"/candidate/{uuid4()}")
    assert r.status_code == 404


def test_post_demo_run_advances_to_deep_scored(client: TestClient) -> None:
    r = client.post("/demo/run")
    assert r.status_code == 200
    body = r.json()
    assert body["state_summary"]["pipeline_phase"] == PipelinePhase.DEEP_SCORED.value

    cand = client.get("/demo/candidate").json()
    assert cand["pipeline_phase"] == PipelinePhase.DEEP_SCORED.value
    hf = cand["skill_summaries"].get("hard_filter") or {}
    assert "decision.summary" in hf or "filter.decision" in str(hf)


def test_post_demo_run_twice_returns_409(client: TestClient) -> None:
    assert client.post("/demo/run").status_code == 200
    r2 = client.post("/demo/run")
    assert r2.status_code == 409


def test_demo_html_contains_profile_phase_timeline_and_scores(client: TestClient) -> None:
    client.post("/demo/run")
    html = client.get("/demo").text
    assert "Alex Morgan" in html
    assert "deep_scored" in html
    assert "workflow timeline" in html
    assert "hard_filter" in html or "filter decision" in html
