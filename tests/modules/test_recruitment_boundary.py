"""Recruitment module boundary and policy smoke tests."""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import integrations.api.session as api_session_module
from integrations.api.app import create_app
from modules.recruitment import policies
from modules.recruitment.runtime import VerticalSliceApiRuntime
from modules.recruitment.use_cases import publish_recruitment_event, record_recruiter_decision, submit_cv
from runtime.bootstrap_vertical_slice import (
    VERTICAL_SLICE_DEFAULT_CANDIDATE_ID,
    VERTICAL_SLICE_INGRESS_EVENT_TYPES,
)
from schemas.governance_schema import GOVERNANCE_EVENT_TYPES


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app(db_path="")) as c:
        yield c


def test_api_session_module_is_shim_only() -> None:
    path = Path(__file__).resolve().parents[2] / "integrations" / "api" / "session.py"
    text = path.read_text(encoding="utf-8")
    assert "class VerticalSliceApiRuntime" not in text
    assert "class DevResetResult" not in text
    assert api_session_module.VerticalSliceApiRuntime is VerticalSliceApiRuntime
    assert api_session_module.DevResetResult is not None


def test_recruitment_module_does_not_import_integrations_api() -> None:
    root = Path(__file__).resolve().parents[2] / "modules" / "recruitment"
    forbidden = "integrations.api"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert forbidden not in alias.name, f"{path.name} imports {alias.name}"
            elif isinstance(node, ast.ImportFrom) and node.module:
                assert forbidden not in node.module, f"{path.name} imports from {node.module}"


def test_governance_payload_not_merged_with_bootstrap_fields() -> None:
    with TestClient(create_app(db_path="")) as client:
        rt = client.app.state.vertical_slice
        payload = {
            "actor_id": "boundary-test",
            "actor_type": "recruiter",
            "reason": "governance boundary test",
            "evidence_refs": ["artifact://test/boundary"],
        }
        result = record_recruiter_decision(
            rt,
            VERTICAL_SLICE_DEFAULT_CANDIDATE_ID,
            "recruiter_schedule_interview",
            payload,
        )
        assert result.ingress_accepted is True
        bus = rt.bundle.bus
        last = bus.recorded_envelopes[-1]
        pl = last.payload
        assert pl.get("bootstrap") is not True
        assert "api_sequence" not in pl
        assert pl["actor_id"] == "boundary-test"


@pytest.mark.parametrize("event_type", list(GOVERNANCE_EVENT_TYPES[:3]))
def test_is_governance_event(event_type: str) -> None:
    assert policies.is_governance_event(event_type)


def test_invalid_candidate_id_via_api_404(client: TestClient) -> None:
    r = client.get(f"/candidate/{uuid4()}")
    assert r.status_code == 404


def test_allowed_ingress_matches_bootstrap_allowlist() -> None:
    assert tuple(policies.ALLOWED_INGRESS_EVENT_TYPES) == VERTICAL_SLICE_INGRESS_EVENT_TYPES
    assert policies.allowed_ingress_event_types() == VERTICAL_SLICE_INGRESS_EVENT_TYPES


def test_submit_cv_delegates_to_publish_recruitment_event() -> None:
    assert submit_cv is not publish_recruitment_event
    assert submit_cv.__doc__ and "Deprecated" in submit_cv.__doc__


def test_api_lifespan_initializes_runtime_and_demo_run(client: TestClient) -> None:
    rt = client.app.state.vertical_slice
    assert isinstance(rt, VerticalSliceApiRuntime)
    assert client.get("/health").status_code == 200
    assert client.post("/demo/run").status_code == 200


def test_admin_reset_restores_new_phase(client: TestClient) -> None:
    assert client.post("/demo/run").status_code == 200
    reset = client.post("/admin/reset")
    assert reset.status_code == 200
    body = reset.json()
    assert body["pipeline_phase"] == "new"
    assert body["status"] == "ok"


def test_non_governance_merge_adds_api_sequence() -> None:
    merged = policies.merge_non_governance_publish_payload(
        {"bootstrap": True, "sequence": 1},
        {"extra": "field"},
        seq=7,
    )
    assert merged["api_sequence"] == 7
    assert merged["extra"] == "field"
    assert merged["bootstrap"] is True
