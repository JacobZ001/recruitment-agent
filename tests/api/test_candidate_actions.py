"""POST /candidates/{id}/action — recruiter governance events from registry."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from modules.recruitment.policies import PRIMARY_VERTICAL_SLICE_EVENT_TYPES
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import (
    DEFAULT_RECRUITER_ACTION_GOVERNANCE_PAYLOAD,
    perform_candidate_action,
    publish_recruitment_event,
)
from runtime.bootstrap_vertical_slice import VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
from schemas.state_schema import PipelinePhase, PipelineState


_GOVERNANCE_PAYLOAD = {
    "actor_id": "api-test-recruiter",
    "actor_type": "recruiter",
    "reason": "API candidate action test",
    "evidence_refs": ["artifact://api/test"],
}


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def _advance_primary_sequence(
    client: TestClient,
    candidate_id: str,
    establish_ready_scoring_context,
) -> None:
    rt = client.app.state.vertical_slice
    establish_ready_scoring_context(rt)
    for event_type in PRIMARY_VERTICAL_SLICE_EVENT_TYPES:
        if event_type == "candidate_created":
            continue
        publish_recruitment_event(rt, UUID(candidate_id), event_type, {})


def test_list_includes_available_actions_with_event_type_keys(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    cid = str(uuid4())
    _advance_primary_sequence(client, cid, establish_ready_scoring_context)
    row = next(x for x in client.get("/candidates").json() if x["candidate_id"] == cid)
    assert row["stage"] == PipelinePhase.SHORTLISTED.value
    keys = {a["key"] for a in row["available_actions"]}
    assert "recruiter_schedule_interview" in keys
    assert all(a["key"] == a["event_type"] for a in row["available_actions"])


def test_action_reject_moves_to_inactive(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    cid = str(uuid4())
    _advance_primary_sequence(client, cid, establish_ready_scoring_context)
    r = client.post(
        f"/candidates/{cid}/action",
        json={"event_type": "recruiter_reject_candidate", "payload": dict(_GOVERNANCE_PAYLOAD)},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == PipelinePhase.INACTIVE.value
    assert body["status"]["kind"] == "inactive"

    list_row = next(x for x in client.get("/candidates").json() if x["candidate_id"] == cid)
    assert list_row["stage"] == PipelinePhase.INACTIVE.value


def test_action_invalid_event_type_for_phase_returns_422(
    client: TestClient,
    establish_ready_scoring_context,
) -> None:
    cid = str(uuid4())
    _advance_primary_sequence(client, cid, establish_ready_scoring_context)
    r = client.post(
        f"/candidates/{cid}/action",
        json={"event_type": "recruiter_complete_interview", "payload": dict(_GOVERNANCE_PAYLOAD)},
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_candidate_action"


def test_action_unknown_candidate_returns_404(client: TestClient) -> None:
    r = client.post(
        f"/candidates/{uuid4()}/action",
        json={"event_type": "recruiter_reject_candidate", "payload": dict(_GOVERNANCE_PAYLOAD)},
    )
    assert r.status_code == 404


def test_action_shortlist_from_deep_scored_moves_to_shortlisted() -> None:
    rt = VerticalSliceApiRuntime()
    cid = uuid4()
    publish_recruitment_event(rt, cid, "candidate_created", {"source": "test"})
    got = rt.bundle.store.get_for_candidate(cid)
    assert got.ok and got.snapshot is not None and got.meta is not None
    deep_scored = got.snapshot.model_copy(
        update={
            "pipeline": PipelineState(
                phase=PipelinePhase.DEEP_SCORED,
                entered_phase_at=got.snapshot.pipeline.entered_phase_at,
            ),
        },
    )
    rep = rt.bundle.store.replace(
        got.snapshot.id,
        deep_scored,
        expected_store_revision=got.meta.store_revision,
    )
    assert rep.ok

    view = perform_candidate_action(
        rt,
        cid,
        "recruiter_shortlist_candidate",
        dict(DEFAULT_RECRUITER_ACTION_GOVERNANCE_PAYLOAD),
    )
    assert view["stage"] == PipelinePhase.SHORTLISTED.value


def test_action_schedule_interview_via_deprecated_action_alias(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert client.post("/demo/run").status_code == 200
    r = client.post(
        f"/candidates/{cid}/action",
        json={"action": "recruiter_schedule_interview", "payload": dict(_GOVERNANCE_PAYLOAD)},
    )
    assert r.status_code == 200
    assert r.json()["stage"] == PipelinePhase.INTERVIEW_PENDING.value
