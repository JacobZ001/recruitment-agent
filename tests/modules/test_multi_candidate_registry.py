"""Multi-candidate mapping and isolation (stateless registry, store-backed reads)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from integrations.api.app import create_app
from modules.recruitment.registry import get_state_id
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import publish_recruitment_event
from runtime.bootstrap_vertical_slice import VERTICAL_SLICE_DEFAULT_CANDIDATE_ID
from schemas.state_schema import PipelinePhase


def test_get_state_id_is_deterministic() -> None:
    cid = uuid4()
    assert get_state_id(cid) == get_state_id(cid)
    assert get_state_id(cid) != get_state_id(uuid4())


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_two_candidates_progress_independently(client: TestClient) -> None:
    cid_a = str(uuid4())
    cid_b = str(uuid4())

    rt = client.app.state.vertical_slice
    publish_recruitment_event(rt, UUID(cid_b), "candidate_created", {"source": "test"})
    publish_recruitment_event(rt, UUID(cid_a), "cv_uploaded", {"source": "test"})

    st_a = client.get(f"/state/{cid_a}")
    st_b = client.get(f"/state/{cid_b}")
    assert st_a.status_code == 200
    assert st_b.status_code == 200
    assert st_a.json()["pipeline_phase"] == PipelinePhase.CV_RECEIVED.value
    assert st_b.json()["pipeline_phase"] == PipelinePhase.NEW.value

    view_a = client.get(f"/candidate/{cid_a}")
    view_b = client.get(f"/candidate/{cid_b}")
    assert view_a.status_code == 200
    assert view_b.status_code == 200
    assert view_a.json()["stage"] == PipelinePhase.CV_RECEIVED.value
    assert view_b.json()["stage"] == PipelinePhase.NEW.value


def test_unknown_candidate_returns_404(client: TestClient) -> None:
    unknown = str(uuid4())
    assert client.get(f"/candidate/{unknown}").status_code == 404
    assert client.get(f"/state/{unknown}").status_code == 404
    assert client.get(f"/timeline/{unknown}").status_code == 404


def test_timeline_non_default_candidate_returns_404_even_with_state(client: TestClient) -> None:
    cid = str(uuid4())
    rt = client.app.state.vertical_slice
    publish_recruitment_event(rt, UUID(cid), "candidate_created", {"source": "test"})
    assert client.get(f"/state/{cid}").status_code == 200
    assert client.get(f"/timeline/{cid}").status_code == 404


def test_timeline_default_candidate_works(client: TestClient) -> None:
    cid = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    tr = client.get(f"/timeline/{cid}")
    assert tr.status_code == 200
    assert "workflow timeline" in tr.json()["timeline_text"]


def test_default_candidate_unchanged_after_multi_candidate(client: TestClient) -> None:
    cid_default = str(VERTICAL_SLICE_DEFAULT_CANDIDATE_ID)
    assert client.get(f"/state/{cid_default}").json()["pipeline_phase"] == PipelinePhase.NEW.value


def test_use_case_isolation_in_runtime() -> None:
    rt = VerticalSliceApiRuntime()
    cid_a = uuid4()
    cid_b = uuid4()
    publish_recruitment_event(rt, cid_a, "candidate_created", {"source": "test"})
    publish_recruitment_event(rt, cid_b, "candidate_created", {"source": "test"})
    publish_recruitment_event(rt, cid_a, "cv_uploaded", {"source": "test"})

    snap_a = rt.bundle.store.get_for_candidate(cid_a).snapshot
    snap_b = rt.bundle.store.get_for_candidate(cid_b).snapshot
    assert snap_a is not None and snap_b is not None
    assert snap_a.pipeline.phase == PipelinePhase.CV_RECEIVED
    assert snap_b.pipeline.phase == PipelinePhase.NEW
    assert get_state_id(cid_a) == snap_a.id
    assert get_state_id(cid_b) == snap_b.id
